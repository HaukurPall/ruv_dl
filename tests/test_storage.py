from ruv_dl.storage import EpisodeDownload, filter_downloaded_episodes


def test_filter_downloaded_all_equal():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == []


def test_filter_downloaded_same_title_and_firstrun():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="2",  # Different id
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == []


def test_filter_downloaded_same_id():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 2",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == []


def test_filter_downloaded_not_same_title_id():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="2",  # Different id
            program_id="1",
            program_title="Program 2",  # Different program_title
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == episodes_to_download


def test_filter_downloaded_same_id_missing_firstrun():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == []


def test_filter_downloaded_not_same_id_missing_firstrun():
    downloaded_episodes = [
        EpisodeDownload(
            id="1",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
        )
    ]
    episodes_to_download = [
        EpisodeDownload(
            id="2",
            program_id="1",
            program_title="Program 1",
            title="Episode 1",
            foreign_title="Foreign title 1",
            quality_str="Quality 1",
            url="Url 1",
            firstrun="Firstrun 1",
        )
    ]
    assert filter_downloaded_episodes(downloaded_episodes, episodes_to_download) == episodes_to_download
