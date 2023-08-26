from pathlib import Path
import pytest
from aimbat.lib import project as lib


class TestProject:

    @pytest.mark.usefixtures("project_directory")
    def test_lib_project(self, project_directory) -> None:  # type: ignore

        self.project_file = Path(f"{project_directory}/aimbat.db")

        assert not self.project_file.exists()
        with pytest.raises(RuntimeWarning):
            lib.project_del(str(self.project_file))

        lib.project_new(str(self.project_file))
        assert self.project_file.exists()

        with pytest.raises(NotImplementedError):
            lib.project_info(str(self.project_file))

        lib.project_del(str(self.project_file))
        assert not self.project_file.exists()

        with pytest.raises(RuntimeError):
            lib.project_info(str(self.project_file))
