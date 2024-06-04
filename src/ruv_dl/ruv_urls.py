import json
import urllib.parse
import httpx


def construct_categories_url(category_type: str):
    base_url = "https://spilari.nyr.ruv.is/gql/"
    operation_name = "getCategories"

    # Convert nested dictionaries to JSON strings
    variables = json.dumps({"type": category_type})
    extensions = json.dumps(
        {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "7d5f9d18d22e7820e095abdce0d97f0bd516e14e0925748cd75ac937d98703db",
            }
        }
    )

    query_params = {"operationName": operation_name, "variables": variables, "extensions": extensions}

    encoded_query_params = urllib.parse.urlencode(query_params)
    full_url = f"{base_url}?{encoded_query_params}"

    return full_url


# Returns a list of categories with the required slug to get the programs.
# Example:
# {
#     "data": {
#         "Category": {
#             "categories": [
#                 {"title": "Annað", "slug": "annad", "__typename": "Category"},
#                 {"title": "Fréttatengt efni", "slug": "frettatengt-efni", "__typename": "Category"},
#                 {"title": "Heimildarefni", "slug": "heimildarefni", "__typename": "Category"},
#                 {"title": "Íþróttir", "slug": "ithrottir", "__typename": "Category"},
#                 {"title": "KrakkaRÚV", "slug": "krakkaruv", "__typename": "Category"},
#                 {"title": "Leikið efni", "slug": "leikid-efni", "__typename": "Category"},
#                 {"title": "Listir", "slug": "listir", "__typename": "Category"},
#                 {"title": "Menning", "slug": "menning", "__typename": "Category"},
#                 {"title": "Samfélag og mannlíf", "slug": "samfelag-og-mannlif", "__typename": "Category"},
#                 {"title": "Skemmtiefni", "slug": "skemmtiefni", "__typename": "Category"},
#                 {"title": "Ungt fólk", "slug": "ungt-folk", "__typename": "Category"},
#             ],
#             "__typename": "CategoryList",
#         }
#     }
# }


def construct_category_url(category: str, station: str):
    base_url = "https://spilari.nyr.ruv.is/gql/"
    operation_name = "getCategory"

    # Convert nested dictionaries to JSON strings
    variables = json.dumps({"category": category, "station": station})
    extensions = json.dumps(
        {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "6ef244edfc897f95aabd1f915d58264329bb64ee498ae8df359ca0fa14c2278a",
            }
        }
    )
    query_params = {"operationName": operation_name, "variables": variables, "extensions": extensions}

    encoded_query_params = urllib.parse.urlencode(query_params)
    full_url = f"{base_url}?{encoded_query_params}"
    return full_url


# Returns a Category with a list of programs, each program has little information and a single episode.
# Example:
# {
#     "data": {
#         "Category": {
#             "categories": [
#                 {
#                     "title": "Fréttatengt efni",
#                     "slug": "frettatengt-efni",
#                     "programs": [
#                         {
#                             "short_description": null,
#                             "episodes": [
#                                 {
#                                     "id": "ahptvh",
#                                     "title": "05.02.2024",
#                                     "rating": 0,
#                                     "__typename": "Episode"
#                                 }
#                             ],
#                             "title": "Kastljós",
#                             "portrait_image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9wb3J0cmFpdF9wb3N0ZXJzL2FocHR2MC0yMG1hMDAuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTAwMCwgImhlaWdodCI6IDE1MDB9fX0=",
#                             "id": 35422,
#                             "slug": "kastljos",
#                             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzL2FocHR2MC1namdyNmcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
#                             "__typename": "Program"
#                         },
#                         ...


base_url = "https://spilari.nyr.ruv.is/gql/"


def construct_serie_url(episode_id: str, program_id: int):
    operation_name = "getSerie"

    variables = json.dumps({"episodeID": [episode_id], "programID": program_id})
    extensions = json.dumps(
        {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "afd9cf0c67f1ebed0a981b72ee127a5a152eb90f4adb2b3bd3e6c1ec185a2dd3",
            }
        }
    )

    query_params = {"operationName": operation_name, "variables": variables, "extensions": extensions}

    encoded_query_params = urllib.parse.urlencode(query_params)
    full_url = f"{base_url}?{encoded_query_params}"

    return full_url


# Returns a Program with a single episode, each episode detailed information and file url.
# Example:
# {
#     "data": {
#         "Program": {
#             "slug": "aevintyri-halldors-gylfasonar",
#             "title": "Ævintýri Halldórs Gylfasonar",
#             "description": "Halldór Gylfason segir sígild ævintýri og leikur jafnframt öll hlutverkin.",
#             "short_description": null,
#             "foreign_title": null,
#             "format": "tv",
#             "id": 26322,
#             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFwMC1ub2JyNGcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
#             "episodes": [
#                 {
#                     "title": "Garðabrúða - seinni hluti",
#                     "id": "7r0qq7",
#                     "description": "Halldór Gylfason leikur öll hlutverk í þessu sígilda ævintýri um stúlkuna sem var með svo sítt hár að hún gat notað það sem reipi til að fá draumaprinsinn sinn í heimsókn upp í turnherbergið sem hún var fangi í.",
#                     "duration": 300,
#                     "firstrun": "2018-01-18T17:29:00",
#                     "scope": "Global",
#                     "file": "https://ruv-vod.akamaized.net/opid/5228824A1/5228824A1.m3u8",
#                     "rating": 0,
#                     "file_expires": "2025-12-31",
#                     "cards": [],
#                     "clips": [],
#                     "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFxNy1kZDRrYW8uanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
#                     "subtitles": [],
#                     "__typename": "Episode"
#                 }
#             ],
#             "__typename": "Program"
#         }
#     }
# }


def construct_episode_url(program_id: int):
    base_url = "https://spilari.nyr.ruv.is/gql/"
    operation_name = "getEpisode"

    # Convert nested dictionaries to JSON strings
    variables = json.dumps({"programID": program_id})
    extensions = json.dumps(
        {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "3c1f5cfa93253b4aabd0f1023be91a30d36ef0acc0d3356aac445d9e005b97f8",
            }
        }
    )
    query_params = {"operationName": operation_name, "variables": variables, "extensions": extensions}

    encoded_query_params = urllib.parse.urlencode(query_params)
    full_url = f"{base_url}?{encoded_query_params}"

    return full_url


# Returns a Program with a list of episodes, each episode has basic information and no file url.
# Example:
# {
#     "data": {
#         "Program": {
#             "slug": "aevintyri-halldors-gylfasonar",
#             "title": "Ævintýri Halldórs Gylfasonar",
#             "description": "Halldór Gylfason segir sígild ævintýri og leikur jafnframt öll hlutverkin.",
#             "short_description": null,
#             "foreign_title": null,
#             "id": 26322,
#             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFwMC1ub2JyNGcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
#             "episodes": [
#                 {
#                     "title": "Garðabrúða - seinni hluti",
#                     "id": "7r0qq7",
#                     "firstrun": "2018-01-18T17:29:00",
#                     "description": "Halldór Gylfason leikur öll hlutverk í þessu sígilda ævintýri um stúlkuna sem var með svo sítt hár að hún gat notað það sem reipi til að fá draumaprinsinn sinn í heimsókn upp í turnherbergið sem hún var fangi í.",
#                     "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFxNy1kZDRrYW8uanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
#                     "__typename": "Episode"
#                 },
#                 ...,
#             ],
#             "__typename": "Program"
#         }
#     }
# }

if __name__ == "__main__":
    category_type = "tv"
    url = construct_categories_url(category_type)
    print(url)
    response = httpx.get(url)
    print(response.json())
    # category = "born"
    # station = "tv"
    # url = construct_category_url(category, station)
    # print(url)
    # response = httpx.get(url)
    # print(response.json())
    # episode_id = "a6t3sd"
    # program_id = 34279
    # url = construct_serie_url(episode_id, program_id)
    # print(url)
    # print(httpx.get(url).json())

    # url = construct_episode_url(33467)
    # print(url)
    # print(httpx.get(url).json())
