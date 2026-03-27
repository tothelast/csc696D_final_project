import pandas as pd
import numpy as np
import os
from datetime import datetime

class RawFile:

    # polish_time (m)
    # remove rate in angstroms / polish_time (a/m)

    def __init__(self, path, wafer_num=1, removal=0, nu=0, wafer_diameter=0.3, pound_force=4.44822, pad_to_wafer=0.225, interval=None, graph_settings=None):
        if interval is None:
            interval = [7, 57]

        # Process Raw Data
        self.file_name = path
        self.file_basename = os.path.basename(path)
        self._date = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d')
        self.raw_data = pd.read_csv(path, sep='\t', header=None, skiprows=1)
        self.process_raw_data()

        # Assign Key attributes
        self._wafer_num = wafer_num
        self._removal = removal
        self._nu = nu
        self._notes = ''
        self._pressure_psi = 0.0
        self._polish_time = 0.0
        self._slurry_type = None
        self._wafer_type = None
        self._pad_type = None
        self._conditioner_disk_type = None
        self.wafer_diameter = wafer_diameter
        self.pound_force = pound_force
        self.pad_to_wafer = pad_to_wafer
        self._interval = interval
        # Graph settings per graph type: {graph_type: {'x_min': ..., 'x_max': ..., 'y_min': ..., 'y_max': ...}}
        # graph_type: 0=COF, 1=Forces, 2=Temperature
        self.graph_settings = graph_settings if graph_settings is not None else {}
        self.hz = self.raw_data['Sampling Rate'][0]

        # Create the green table on the right and the final row for the report
        self.total_per_frame = self.populate_total_per_frame()
        self.final_row = self.calculate_final_raw()

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        """Set interval and recalculate final_row."""
        self._interval = value
        if hasattr(self, 'total_per_frame'):
            self.final_row = self.calculate_final_raw()

    @property
    def removal(self):
        return self._removal

    @removal.setter
    def removal(self, value):
        """Set removal and update final_row."""
        self._removal = value
        if hasattr(self, 'final_row'):
            self.final_row['Removal'] = value
            self._update_removal_rate()

    @property
    def nu(self):
        return self._nu

    @nu.setter
    def nu(self, value):
        """Set WIWNU and update final_row."""
        self._nu = value
        if hasattr(self, 'final_row'):
            self.final_row['WIWNU'] = value

    @property
    def notes(self):
        return self._notes

    @notes.setter
    def notes(self, value):
        """Set notes and update final_row."""
        self._notes = value
        if hasattr(self, 'final_row'):
            self.final_row['Notes'] = value

    @property
    def slurry_type(self):
        return self._slurry_type

    @slurry_type.setter
    def slurry_type(self, value):
        self._slurry_type = value

    @property
    def wafer_type(self):
        return self._wafer_type

    @wafer_type.setter
    def wafer_type(self, value):
        self._wafer_type = value

    @property
    def pad_type(self):
        return self._pad_type

    @pad_type.setter
    def pad_type(self, value):
        self._pad_type = value

    @property
    def conditioner_disk_type(self):
        return self._conditioner_disk_type

    @conditioner_disk_type.setter
    def conditioner_disk_type(self, value):
        self._conditioner_disk_type = value

    @property
    def pressure_psi(self):
        return self._pressure_psi

    @pressure_psi.setter
    def pressure_psi(self, value):
        self._pressure_psi = value
        if hasattr(self, 'final_row'):
            self.final_row['Pressure PSI'] = value
            self._update_removal_rate()

    @property
    def polish_time(self):
        return self._polish_time

    @polish_time.setter
    def polish_time(self, value):
        self._polish_time = value
        if hasattr(self, 'final_row'):
            self.final_row['Polish Time'] = value
            self._update_removal_rate()

    def _update_removal_rate(self):
        """Recalculate Removal Rate from removal and polish_time."""
        if hasattr(self, 'final_row'):
            rate = self._removal / self._polish_time if self._polish_time > 0 else 0
            self.final_row['Removal Rate'] = rate

    @property
    def wafer_num(self):
        return self._wafer_num

    @wafer_num.setter
    def wafer_num(self, value):
        """Set wafer number and update final_row."""
        self._wafer_num = value
        if hasattr(self, 'final_row'):
            self.final_row['Wafer #'] = value

    def get_metadata(self):
        """Return metadata dictionary for Excel export."""
        return {
            'Wafer Diameter (m)': self.wafer_diameter,
            'Area (m²)': self.calculate_area(),
            'Pad to Wafer Ratio': self.pad_to_wafer,
            'Baseline Fy (lbf)': self.calculate_baseline_fy(),
            'Baseline Fz (lbf)': self.calculate_baseline_fz()
        }

    def to_dict(self, project_dir=None):
        """Serialize RawFile to dictionary for saving.

        Args:
            project_dir: If provided, save file_name as relative path from project_dir
        """
        file_name = self.file_name

        # Convert to relative path if project_dir is provided
        if project_dir:
            try:
                file_name = os.path.relpath(self.file_name, project_dir)
            except (ValueError, TypeError):
                # Keep absolute path if conversion fails
                pass

        return {
            'file_name': file_name,
            'wafer_num': self.wafer_num,
            'removal': self._removal,
            'nu': self._nu,
            'notes': self._notes,
            'wafer_diameter': self.wafer_diameter,
            'pound_force': self.pound_force,
            'pad_to_wafer': self.pad_to_wafer,
            'interval': self._interval,
            'graph_settings': self.graph_settings,
            'slurry_type': self._slurry_type,
            'wafer_type': self._wafer_type,
            'pad_type': self._pad_type,
            'conditioner_disk_type': self._conditioner_disk_type,
            'pressure_psi': self._pressure_psi,
            'polish_time': self._polish_time,
            'date': self._date
        }

    @classmethod
    def from_dict(cls, data, project_dir=None):
        """Deserialize RawFile from dictionary.

        Args:
            data: Dictionary containing RawFile data
            project_dir: If provided, resolve relative paths from this directory
        """
        file_path = data['file_name']

        # Resolve relative path if project_dir is provided and path is relative
        if project_dir and not os.path.isabs(file_path):
            file_path = os.path.join(project_dir, file_path)

        instance = cls(
            path=file_path,
            wafer_num=data['wafer_num'],
            removal=data['removal'],
            nu=data['nu'],
            wafer_diameter=data['wafer_diameter'],
            pound_force=data['pound_force'],
            pad_to_wafer=data['pad_to_wafer'],
            interval=data['interval'],
            graph_settings=data.get('graph_settings', {})
        )
        instance.notes = data.get('notes', '')
        instance.slurry_type = data.get('slurry_type')
        instance.wafer_type = data.get('wafer_type')
        instance.pad_type = data.get('pad_type')
        instance.conditioner_disk_type = data.get('conditioner_disk_type')
        instance.pressure_psi = data.get('pressure_psi', 0.0)
        instance.polish_time = data.get('polish_time', 0.0)
        if 'date' in data:
            instance._date = data['date']
            instance.final_row['Date'] = data['date']
        return instance

    def process_raw_data(self):
        self.raw_data = self.raw_data.T
        self.raw_data.columns = ['IR Temperature', 'Fy', 'Fz1', 'Fz2', 'Flowrate 1', 'Flowrate 2', 'Flowrate 3', 'Wafer RPM', 'Pad RPM', 'Cond. RPM', 'N/A', 'N/A', 'Sampling Rate', 'N/A', 'Baseline Fy', 'Baseline Fz', 'Number of Baseline', 'Fz3', 'Fz4', 'Cond. Motor Current', 'Platen Motor Current', 'Carrier Motor Current']

    def calculate_baseline_fy(self):
        baseline_Fy = np.average(self.raw_data['Baseline Fy'][self.raw_data['Baseline Fy'] != 0])
        return baseline_Fy

    def calculate_baseline_fz(self):
        baseline_Fz_list = self.raw_data['Baseline Fz'][self.raw_data['Baseline Fz'] != 0]
        size_of_one = len(baseline_Fz_list) / 4
        size_of_one = int(size_of_one)
        baseline_Fz = np.sum([
            np.average(baseline_Fz_list[:size_of_one]),
            np.average(baseline_Fz_list[size_of_one:size_of_one*2]),
            np.average(baseline_Fz_list[size_of_one*2:size_of_one*3]),
            np.average(baseline_Fz_list[size_of_one*3::])
        ])
        return baseline_Fz

    def calculate_area(self):
        area = np.pi * (self.wafer_diameter/2)**2
        return area

    def calculate_fz_total_lbf(self):
        '(Fz1 + Fz2 + Fz3 + Fz4) - baseline_Fz'
        return self.raw_data[['Fz1', 'Fz2', 'Fz3', 'Fz4']].sum(axis=1) - self.calculate_baseline_fz()

    def calculate_fy_total_lbf(self):
        'Fy - baselineFy'
        return self.raw_data['Fy'] - self.calculate_baseline_fy()

    def calculate_fz_total_N(self):
        'fz_total_lbf * pound force'
        return self.calculate_fz_total_lbf() * self.pound_force

    def calculate_fy_total_N(self):
        'fy_total_lbf * pound force'
        return self.calculate_fy_total_lbf() * self.pound_force

    def calculate_pressure(self):
        'fz_total_N / area'
        return self.calculate_fz_total_N() / self.calculate_area()

    def calculate_cof(self):
        'fy_total_lbf / fz_total_lbf'
        return self.calculate_fy_total_lbf() / self.calculate_fz_total_lbf()

    def calculate_pad_rotation_rate(self):
        '(pad_rpm * 2 * pi) / 60'
        return (self.raw_data['Pad RPM'] * 2 *np.pi) / 60

    def calculate_average_nominal_wafer_sliding_velocity(self):
        'pad_rotation_rate * pad_to_wafer'
        return self.calculate_pad_rotation_rate() * self.pad_to_wafer

    def calculate_v_p(self):
        'average_nominal_wafer_sliding_velocity / pressure'
        return self.calculate_average_nominal_wafer_sliding_velocity() / self.calculate_pressure()

    def calculate_p_v(self):
        'average_nominal_wafer_sliding_velocity * pressure'
        return self.calculate_average_nominal_wafer_sliding_velocity() * self.calculate_pressure()

    def calculate_cof_p_v(self):
        'cof * p_v'
        return self.calculate_cof() * self.calculate_p_v()

    def populate_total_per_frame(self):
        num_rows = len(self.raw_data)
        time_interval = 1 / self.hz
        time_values = np.arange(num_rows) * time_interval
        p = pd.DataFrame({'time (s)': time_values})
        p['Fz Total (lbf)'] = self.calculate_fz_total_lbf()
        p['Fy Total (lbf)'] = self.calculate_fy_total_lbf()
        p['1 pound force = N'] = self.pound_force
        p['Fz Total (N)'] = self.calculate_fz_total_N()
        p['Fy Total (N)'] = self.calculate_fy_total_N()
        if 'IR Temperature' in self.raw_data.columns:
            p['IR Temperature'] = self.raw_data['IR Temperature']
        p['Pressure (Pa)'] = self.calculate_pressure()
        p['COF'] = self.calculate_cof()
        p['Pad Rotation Rate (Rad/s)'] = self.calculate_pad_rotation_rate()
        p['Average Nominal Wafer Sliding Velocity (m/s)'] = self.calculate_average_nominal_wafer_sliding_velocity()
        p['v / P (m/Pas.s)'] = self.calculate_v_p()
        p['P.V (m.Pa/s)'] = self.calculate_p_v()
        p['COF.P.V (m.Pa/s)'] = self.calculate_cof_p_v()
        return p

    def calculate_final_raw(self):
        # Clamp indices to valid bounds to prevent IndexError on short files
        n_frames = len(self.total_per_frame)
        n_raw = len(self.raw_data)
        start_idx = max(0, min(int(self._interval[0] * self.hz), n_frames - 1))
        end_idx = max(start_idx, min(int(self._interval[1] * self.hz), n_frames - 1))
        raw_start = max(0, min(start_idx, n_raw - 1))
        raw_end = max(raw_start, min(end_idx, n_raw - 1))
        # Use file_basename (without extension) for cleaner display
        display_name = os.path.splitext(self.file_basename)[0]
        final_row = pd.DataFrame({
            'Date': [self._date],
            'File Name': [display_name],
            'Wafer #': [self.wafer_num],
            'COF': [self.total_per_frame['COF'].iloc[start_idx:end_idx+1].mean()],
            'Fy': [self.total_per_frame['Fy Total (lbf)'].iloc[start_idx:end_idx+1].mean()],
            'Var Fy': [self.total_per_frame['Fy Total (lbf)'].iloc[start_idx:end_idx+1].var()],
            'Fz': [self.total_per_frame['Fz Total (lbf)'].iloc[start_idx:end_idx+1].mean()],
            'Var Fz': [self.total_per_frame['Fz Total (lbf)'].iloc[start_idx:end_idx+1].var()],
            'Mean Temp': [self.raw_data['IR Temperature'].iloc[raw_start:raw_end+1].mean()],
            'Init Temp': [self.raw_data['IR Temperature'].iloc[raw_start]],
            'High Temp': [self.raw_data['IR Temperature'].iloc[raw_start:raw_end+1].max()],
            'Removal': [self._removal],
            'WIWNU': [self._nu],
            'Mean Pressure': [self.total_per_frame['Pressure (Pa)'].iloc[start_idx:end_idx+1].mean()],
            'Mean Velocity': [self.total_per_frame['Average Nominal Wafer Sliding Velocity (m/s)'].iloc[start_idx:end_idx+1].mean()],
            'P.V': [self.total_per_frame['P.V (m.Pa/s)'].iloc[start_idx:end_idx+1].mean()],
            'COF.P.V': [self.total_per_frame['COF.P.V (m.Pa/s)'].iloc[start_idx:end_idx+1].mean()],
            'Sommerfeld': [self.total_per_frame['v / P (m/Pas.s)'].iloc[start_idx:end_idx+1].mean()],
            'Pressure PSI': [self._pressure_psi],
            'Polish Time': [self._polish_time],
            'Removal Rate': [self._removal / self._polish_time if self._polish_time > 0 else 0],
            'Notes': [self._notes]
        })
        return final_row






