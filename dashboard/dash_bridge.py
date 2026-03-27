import pandas as pd

class DataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance.current_report = None
        return cls._instance

    def update_report(self, report):
        """Update the current report reference."""
        self.current_report = report

    def get_all_data(self):
        """
        Get aggregated data for all files in the report.
        Returns a DataFrame with calculated metrics for each file.
        """
        if not self.current_report or not self.current_report.files:
            return pd.DataFrame()

        data = []
        # Sort files by basename for consistent ordering
        sorted_files = sorted(self.current_report.files, key=lambda f: f.file_basename.lower())
        for raw_file in sorted_files:
            # Use final_row for summary metrics
            row = raw_file.final_row.iloc[0].to_dict()
            # Ensure File Name matches the unique identifier used in dropdowns (basename with extension)
            row['File Name'] = raw_file.file_basename
            # Add file object reference if needed, or just ID
            row['file_id'] = id(raw_file)
            row['Slurry'] = raw_file.slurry_type or ''
            row['Wafer'] = raw_file.wafer_type or ''
            row['Pad'] = raw_file.pad_type or ''
            row['Conditioner'] = raw_file.conditioner_disk_type or ''
            data.append(row)

        return pd.DataFrame(data)

    def get_file_data(self, file_basename):
        """
        Get detailed time-series data for a specific file.
        Returns the total_per_frame DataFrame for the file.
        """
        if not self.current_report:
            return None

        for raw_file in self.current_report.files:
            if raw_file.file_basename == file_basename:
                return raw_file.total_per_frame

        return None

    def get_file_interval(self, file_basename):
        """Get the interval [start, end] in seconds for a specific file."""
        if not self.current_report:
            return None
        for raw_file in self.current_report.files:
            if raw_file.file_basename == file_basename:
                return raw_file.interval
        return None

    def get_file_names(self):
        """Get list of available file names."""
        if not self.current_report:
            return []
        # Sort files by basename for consistent ordering
        sorted_files = sorted(self.current_report.files, key=lambda f: f.file_basename.lower())
        return [f.file_basename for f in sorted_files]
