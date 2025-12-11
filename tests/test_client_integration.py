import pytest

from ruv_dl import ruv_client


@pytest.mark.slow
@pytest.mark.asyncio
async def test_get_all_programs_structure():
    """Test that get_all_programs returns expected data structure"""
    async with ruv_client.RUVClient() as client:
        programs = await client.get_all_programs()
        assert len(programs) > 0
        assert isinstance(programs, dict)

        # Check a few programs to ensure structure is correct
        for program_id, program in list(programs.items())[:5]:
            assert isinstance(program_id, (str, int)), f"Program ID should be string or int: {program_id}"
            assert program["title"], f"Bad program: {program}"
            assert program["id"], f"Bad program: {program}"
            assert "episodes" in program, f"Bad program: {program}"
            assert isinstance(program["episodes"], list), f"Episodes should be list: {program}"

            # Some programs have no episodes, but if they do, check structure
            # Note: get_all_programs() only returns episode IDs, not full details
            for episode in program["episodes"]:
                assert "id" in episode, f"Bad episode: {episode}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_get_program_episodes_with_files():
    """Test that get_program_episodes returns episodes with file URLs"""
    async with ruv_client.RUVClient() as client:
        # First get some programs
        programs = await client.get_all_programs()

        # Find a program with episodes
        test_program_id = None
        for program in programs.values():
            if program["episodes"]:
                test_program_id = program["programID"]
                break

        assert test_program_id is not None, "No programs with episodes found"

        # Get detailed episodes
        detailed_programs = await client.get_programs_with_episodes([test_program_id])
        assert len(detailed_programs) > 0

        program = list(detailed_programs.values())[0]
        assert "episodes" in program

        # Check that episodes have file URLs
        for episode in program["episodes"]:
            assert "id" in episode, f"Episode missing id: {episode}"
            assert "title" in episode, f"Episode missing title: {episode}"
            assert "file" in episode, f"Episode missing file URL: {episode}"
            assert "firstrun" in episode, f"Episode missing firstrun: {episode}"
            assert "file_expires" in episode, f"Episode missing file_expires: {episode}"

            # Validate file URL format
            file_url = episode["file"]
            assert file_url.startswith("https://"), f"Invalid file URL: {file_url}"
            assert ".m3u8" in file_url, f"File URL should be HLS stream: {file_url}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_api_endpoints_accessible():
    """Test that all API endpoints are accessible and return valid responses"""
    async with ruv_client.RUVClient() as client:
        # Test categories endpoint
        categories = await client.get_categories()
        assert len(categories) > 0
        assert all("title" in cat and "slug" in cat for cat in categories)

        # Test category programs endpoint
        first_category = categories[0]
        programs = await client.get_category_programs(first_category["slug"])
        assert isinstance(programs, list)

        # Test program episodes endpoint (if programs exist)
        if programs:
            first_program = programs[0]
            program_id = first_program["id"]
            program_detail = await client.get_program_episodes(program_id)
            if program_detail:  # Some programs might not have episodes
                assert "episodes" in program_detail
                assert isinstance(program_detail["episodes"], list)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_required_program_fields():
    """Test that programs contain all required fields for the application"""
    async with ruv_client.RUVClient() as client:
        programs = await client.get_all_programs()

        # Test first few programs for required fields
        for program in list(programs.values())[:3]:
            # Required fields that the app depends on
            assert "id" in program
            assert "title" in program
            assert "episodes" in program

            # Check for programID field which is used in some functions
            if "programID" in program:
                assert isinstance(program["programID"], int)

            # Optional but commonly used fields
            expected_optional_fields = ["foreign_title", "short_description"]
            for field in expected_optional_fields:
                if field in program:
                    # If present, should not be empty string (None is OK)
                    if program[field] is not None:
                        assert program[field] != ""


@pytest.mark.slow
@pytest.mark.asyncio
async def test_post_getprogram_episodes_directly():
    """Test the POST-based getEpisode function directly"""
    async with ruv_client.RUVClient() as client:
        try:
            # Use a known program ID from previous tests
            result = await client.get_program_episodes(32122)

            # Verify the response structure
            assert result is not None, "Should return program data"
            assert "episodes" in result, "Should contain episodes"
            assert isinstance(result["episodes"], list), "Episodes should be a list"
            assert "title" in result, "Program should have title"
            assert "id" in result, "Program should have id"

            # Check that episodes now contain file and file_expires
            if result["episodes"]:
                first_episode = result["episodes"][0]
                assert "file" in first_episode, f"Episode missing file URL: {first_episode}"
                assert "file_expires" in first_episode, f"Episode missing file_expires: {first_episode}"

        except ruv_client.RUVAPIError as e:
            pytest.fail(f"POST getEpisode failed: {e}")

            pytest.fail(f"Unexpected error type: {type(e).__name__}: {e}")
