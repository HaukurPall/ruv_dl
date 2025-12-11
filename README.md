# RÚV-DL

RÚV-DL (`ruv-dl`) is terminal line client for downloading content from [RÚV](https://ruv.is/).

It handles the following tasks:

- Query RÚV graphql API for program information
- Wraps ffmpeg to download the video files
- Caches and keeps track of downloaded files
- Assist with some common management tasks

# Installation

- Python version 3.8
- [ffmpeg](https://www.ffmpeg.org/download.html)

Be sure to add `ffmpeg` to `PATH`, especially windows users.

And then:

```
pip install git+https://github.com/HaukurPall/ruv_dl
```

## Motivation

This projected is motivated by [ruvsarpur](https://github.com/sverrirs/ruvsarpur).
The original plan was to fork that repo and improve upon it, but it was easier to approch the problem from scratch.

## Versions

- 1.3.0: Removed `organize` and `split-episode` commands to simplify the codebase. Fixed intermittent `PersistedQueryNotFound` errors by switching from GET requests with persisted query hashes to POST requests with full GraphQL queries.
- 1.2.0: Added support for subtitles. If subtitles are available they are downloaded and embedded into the video file. Large refactoring of the RÚV client.
- 1.1.2: Fixed (silent - but deadly) error when downloading program list from RÚV, after RÚV updated. Reoccurring issues will still be silent which needs to be resolved later. Introduces a new approach to fetching programs and episodes from RÚV which is more efficient than the previous one.
- 1.1.1: Fixed incorrect stream indexing (of quality) which resulted in a crash and incorrect video quality, after RÚV updated.
- 1.1.0: Improved download tracking. Now we compare the program title and the episode's firstrun date to see if the file is already downloaded. This is to avoid downloading the same file multiple times, even when they have different ids (according to RÚV).
- 1.0.0: Initial release. Search, download and download tracking.

# Usage

This program is not as fully featured as the original ruvsarpur but it has these benefits:

- Faster downloading of the available programs on ruv.is
- More available tv programs and radio shows and podcasts.
- Simple terminal client; `ruv-dl`.

Example usage: Download all episodes of a single program.

```bash
ruv-dl search "hvolpasveitin" --ignore-case --only-ids | ruv-dl download-program
```

This will:

- Search through all the programs available for the search term.
- Output the program ids found and pipe them to the next command.
- The second command will download all missing episodes (not previously downloaded) of those programs.

As a side-effect, some files are generated in the **current working directory** in process:

- `downloads/` folder, contains the downloaded files
- `debug.log` file, logging information from the program
- `downloaded.jsonl` file, contains information about the programs downloaded

## Main command

`ruv-dl` is the main command.
It takes two options:

- `--work-dir`: The working directory where the program will store its files. By default, the current working directory.
- `--log-level`: The log level. By default it is `WARNING`.

For more details see `ruv-dl --help` or any of the subcommands' help `ruv-dl <subcommand> --help`.

All the following commands are subcommands of `ruv-dl`.

## `search`

The search command is used to search for programs.
It can take multiple search terms and will output a nice table with the programs found.
If the search term contains spaces, be sure to wrap it in quotes.
The command searches for substring matches in the program title and foreign title (if any).

The search command takes the following options:

- `--ignore-case`: Ignore case when searching.
- `--only-ids`: Only output the program ids found, not a nice table. This is useful for piping the ids to the next command.

An example usage of searching using multiple search terms and `--ignore-case`:

```bash
ruv-dl search "hvolpa" "sámur" "skotti" "lestrarhvutti" "úmísúmí" "kúlu" "klingjur" "teitur" "blæja" "hrúturinn" --ignore-case
# prints
| Program title                   | Foreign title             |   Episode count |   Program ID | Short description                        |
|---------------------------------|---------------------------|-----------------|--------------|------------------------------------------|
| Hvolpasveitin                   | Paw Patrol VII            |               5 |        31660 | Hvolparnir síkátu halda áfram ævintýrum  |
| Hvolpasveitin                   | Paw Patrol VI             |               8 |        31659 | Sjötta serían af Hvolpsveitinni þar sem  |
| Hæ Sámur                        | Hey Duggee                |               6 |        30699 | Vinalegi hundurinn Sámur hvetur börn til |
| Skotti og Fló                   | Munki and Trunk           |              12 |        30275 | Apinn Skotti og fíllinn Fló eru bestu vi |
| Lestrarhvutti                   | Dog Loves Books           |               2 |        29782 | Hvutti og Kubbur dýrka bækur og á bókasa |
| Úmísúmí                         | Team Umizoomi I           |               1 |        30265 | Stærðfræðiofurhetjurnar Millý, Geó og Bó |
| Kúlugúbbarnir                   | Bubble Guppies III        |               4 |        30227 | Krúttlegir teiknimyndaþættir um litla ha |
| Teitur í jólaskapi              | Timmy: Christmas Surprise |               1 |        32517 | Það er aðfangadagur í leikskólanum hjá T |
| Blæja                           | Bluey                     |              12 |        31684 | Blæja er sex ára hundur sem er stútfull  |
| Hrúturinn Hreinn: Björgun Teits |                           |               1 |        32509 | Hreinn og vinir hans leggjast í leiðangu |
```

## `download-program`

The download command is used to download all missing episodes of a program into `downloads/`.
It takes program ids as arguments.

It takes the following options:

- `--quality`: The video quality to download. By default, it is `1080p`, but you can also use `720p`, `480p`, `360p` and `240p`.

The easiest way to download programs is to append `--only-ids` to the `search` command and pipe it to the `download-program` command:

```
ruv-dl search "hvolpa" "sámur" "blæja" --ignore-case --only-ids | ruv-dl download-program
# prints
Downloading Blæja - Þáttur 8 af 52: 100%|████████████| 2/2 [00:44<00:00, 22.29s/it]
...
```

These shows are now present in the `downloads/` folder.

```
$ ls downloads/
Blæja ||| Þáttur 8 af 52 ||| Bluey [1080p].mp4  Blæja ||| Þáttur 9 af 52 ||| Bluey [1080p].mp4
```

The naming convention of the downloaded files is:
`Program title ||| Episode title ||| foreign title [QUALITY].mp4`

### The `downloaded.jsonl` file

When the download command is run, it will create a `downloaded.jsonl` file.
This file contains information about the episodes downloaded and is used to avoid downloading the same episode again.

If you want to re-download all episodes, you can delete the `downloaded.jsonl` file and run the `download-program` command again.
If you want to re-download a single episodes, you can find the corresponding line in the file and delete it and run the `download-program` command again.



## Development

If you are interested in this project; check out the code, open up issues and send PRs.

### Debugging

Check the `debug.log` file for more information and/or increase the `--log-level` to `DEBUG` to see more in the stderr.

The `debug.log` file is rotated, so it will not grow indefinitely.



### `schema.graphql`

There is a graphql schema within the project, but it is not the official schema.
It is hand-constructed since the endpoint disallows introspection.
Therefore, it might contain errors and is not used to validate the queries.

## Disclaimer

You are not the owner/copyright holder of the content you download and neither am I.
You are not allowed to distribute the content you download.
You are expected to delete the content when it is no longer available on RÚV. A feature to delete the content is planned.
