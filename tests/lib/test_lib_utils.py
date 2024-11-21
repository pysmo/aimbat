class TestLibUtils:
    def test_plotseis(self, sac_file_good, mock_show) -> None:  # type: ignore
        from aimbat.lib import project, data, utils

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")
        utils.utils_plotseis(1)
