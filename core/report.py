import pandas as pd
from core.raw_file import RawFile

class Report():
    def __init__(self):
        self.files = []
        self.final_data = pd.DataFrame()

    def add_file(self, file):
        self.files.append(file)

    def remove_file(self, file):
        """Remove a file from the report."""
        if file in self.files:
            self.files.remove(file)

    def generate_report(self):
        """Generate the final report from all files."""
        self.final_data = pd.DataFrame()
        # Sort files by basename for consistent ordering (matches UI display)
        sorted_files = sorted(self.files, key=lambda f: f.file_basename.lower())
        for file in sorted_files:
            self.final_data = pd.concat([self.final_data, file.final_row], ignore_index=True)
        return self.final_data

    def to_dict(self, project_dir=None):
        """Serialize Report to dictionary for saving.

        Args:
            project_dir: If provided, save file paths as relative to this directory
        """
        return {
            'files': [f.to_dict(project_dir) for f in self.files]
        }

    @classmethod
    def from_dict(cls, data, project_dir=None):
        """Deserialize Report from dictionary.

        Args:
            data: Dictionary containing Report data
            project_dir: If provided, resolve relative file paths from this directory
        """
        instance = cls()
        for file_data in data.get('files', []):
            try:
                raw_file = RawFile.from_dict(file_data, project_dir)
                instance.add_file(raw_file)
            except Exception as e:
                print(f"Error loading file {file_data.get('file_name', 'unknown')}: {e}")
        return instance
