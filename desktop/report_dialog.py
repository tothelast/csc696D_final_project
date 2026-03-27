"""Report Dialog - Excel export functions for report generation."""

import os
import pandas as pd


REPORT_COLUMN_LABELS = {
    'Date': 'Date',
    'File Name': 'File Name',
    'Wafer #': 'Wafer #',
    'COF': 'Mean COF',
    'Fy': 'Mean Fy (lbf)',
    'Var Fy': 'Var Fy (lbf\u00b2)',
    'Fz': 'Mean Fz (lbf)',
    'Var Fz': 'Var Fz (lbf\u00b2)',
    'Mean Temp': 'Mean Pad Temp (\u00b0C)',
    'Init Temp': 'Init Pad Temp (\u00b0C)',
    'High Temp': 'High Pad Temp (\u00b0C)',
    'Removal': 'Removal (\u00c5)',
    'WIWNU': 'WIWNU (%)',
    'Mean Pressure': 'Mean Pressure (Pa)',
    'Mean Velocity': 'Mean Sliding Velocity (m/s)',
    'P.V': 'P\u00b7V (Pa\u00b7m/s)',
    'COF.P.V': 'COF\u00b7P\u00b7V (Pa\u00b7m/s)',
    'Sommerfeld': 'Sommerfeld Number (m/Pa\u00b7s)',
    'Pressure PSI': 'Pressure (PSI)',
    'Polish Time': 'Polish Time (min)',
    'Removal Rate': 'Removal Rate (\u00c5/min)',
    'Notes': 'Notes',
}


def create_detailed_excel(report, file_path, progress_callback=None, save_callback=None):
    """Create detailed Excel file with one sheet per raw file.

    Layout: Raw data on left, metadata in middle, total_per_frame on right.
    Uses xlsxwriter for fast performance with large datasets.

    Args:
        progress_callback: Optional callable(current, total) called after each file sheet is written.
        save_callback: Optional callable() called after all sheets are written, before workbook flush.
    """
    sorted_files = sorted(report.files, key=lambda f: f.file_basename.lower())
    total = len(sorted_files)

    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        workbook = writer.book

        # Define formats
        header_format = workbook.add_format({
            'bold': True, 'font_size': 10,
            'bg_color': '#D9E2F3', 'border': 1
        })
        metadata_key_format = workbook.add_format({
            'bold': True, 'font_size': 10,
            'bg_color': '#FFC000', 'border': 1
        })
        metadata_value_format = workbook.add_format({
            'bg_color': '#FFEB9C', 'border': 1
        })

        for file_idx, raw_file in enumerate(sorted_files):
            sheet_name = os.path.splitext(raw_file.file_basename)[0][:31]

            # Write raw_data DataFrame (starts at row 0, col 0)
            raw_file.raw_data.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0, startcol=0)

            # Write total_per_frame DataFrame
            raw_data_cols = len(raw_file.raw_data.columns)
            metadata_start_col = raw_data_cols + 1
            total_per_frame_start_col = metadata_start_col + 3  # +2 for metadata columns, +1 for gap
            raw_file.total_per_frame.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0, startcol=total_per_frame_start_col)

            # Get worksheet for additional formatting
            worksheet = writer.sheets[sheet_name]

            # Style headers for raw_data
            for col_idx, col_name in enumerate(raw_file.raw_data.columns):
                worksheet.write(0, col_idx, col_name, header_format)

            # Style headers for total_per_frame
            for col_idx, col_name in enumerate(raw_file.total_per_frame.columns):
                worksheet.write(0, total_per_frame_start_col + col_idx, col_name, header_format)

            # Write metadata section
            metadata_items = [
                ("Wafer Diameter (m)", raw_file.wafer_diameter),
                ("", ""),
                ("Area = \u03c0 \u00d7 (Wafer Diameter / 2)\u00b2", ""),
                ("Area (m\u00b2)", raw_file.calculate_area()),

                ("Pad to Wafer Ratio", raw_file.pad_to_wafer),
                ("", ""),

                ("Baseline Fy (lbf)=", raw_file.calculate_baseline_fy()),
                ("Baseline Fz (lbf)=", raw_file.calculate_baseline_fz()),
            ]

            for row_idx, (key, value) in enumerate(metadata_items):
                if key:
                    worksheet.write(row_idx, metadata_start_col, key, metadata_key_format)
                    if value != "":
                        worksheet.write(row_idx, metadata_start_col + 1, value, metadata_value_format)

            # Set column widths based on header lengths
            for col_idx, col_name in enumerate(raw_file.raw_data.columns):
                worksheet.set_column(col_idx, col_idx, max(len(str(col_name)) + 2, 10))

            worksheet.set_column(metadata_start_col, metadata_start_col + 1, 25)

            for col_idx, col_name in enumerate(raw_file.total_per_frame.columns):
                worksheet.set_column(total_per_frame_start_col + col_idx, total_per_frame_start_col + col_idx, max(len(str(col_name)) + 2, 10))

            if progress_callback:
                progress_callback(file_idx + 1, total)

        if save_callback:
            save_callback()


def create_summary_excel(report, file_path):
    """Create summary Excel file with final report."""
    report_df = report.generate_report().rename(columns=REPORT_COLUMN_LABELS)

    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        report_df.to_excel(writer, sheet_name='Report', index=False)
        worksheet = writer.sheets['Report']

        # Set column widths based on header lengths
        for col_idx, col_name in enumerate(report_df.columns):
            worksheet.set_column(col_idx, col_idx, max(len(str(col_name)) + 2, 10))


