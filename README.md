# RÚV-DL

This projected is motivated by https://github.com/sverrirs/ruvsarpur.
The original plan was to fork that repo and improve upon it, but it was easier to approch the problem from scratch.

RÚV-DL is

- A specialized RÚV graphql client
- A wrapper around ffmpeg
- A book-keeper

# Installation

- Python version 3.8
- [ffmpeg](https://www.ffmpeg.org/download.html)

Be sure to add ffmpeg to `PATH`, especially windows users.

And then:

```
pip install git+https://github.com/HaukurPall/ruv_dl
```

# Usage

This program is not as fully featured as the original ruvsarpur but it has these benefits:

- Faster downloading of the available programs on ruv.is
- More available tv programs and radio shows and podcasts.
- Simple terminal client; `ruv`.

Example usage: Download all episodes of a single program.

```bash
ruv search "hvolpasveitin" --ignore-case --only-ids | ruv download-program
```

This will:

- Search through all the programs available for the search term.
- Output the program ids found and pipe them to the next command.
- The second command will download all missing episodes (not previously downloaded) of those programs.

As a side-effect, some files are generated in the current working directory in process:

- `downloads/` folder, contains the downloaded files
- `organized/` folder, explained in the [organize](##organize) section.
- `programs.json` file, contains information about all the programs fetched
- `programs_last_fetched.txt` file, a timestamp for when we fetched the `programs.json`
- `debug.log` file, logging information from the program
- `downloaded.jsonl` file, contains information about the programs downloaded

## Search

```
ruvsarpur --work-dir $PWD search "hvolpa" "sámur" "skotti" "lestrarhvutti" "úmísúmí" "kúlu" "klingjur" "teitur" "blæja" "hrúturinn" --ignore-case
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

## Download

To download shows you supply the `download-program` command a list of program ids to download.

The easiest way to do this is to append `--only-ids` to the search command and pipe it to the `download-program` command:

```
ruvsarpur --work-dir $PWD search "hvolpa" "sámur" "skotti" "lestrarhvutti" "úmísúmí" "kúlu" "klingjur" "teitur" "blæja" "hrúturinn" --ignore-case --only-ids | ruvsarpur --work-dir $PWD download-program
```

### Keeping track of downloaded shows

The script keeps track of the shows that have already been downloaded so that you do not download them again.

TODO: Explain how.

### Choosing video quality

The script automatically attempts to download videos using the highest video quality for all download streams, this is equivilent of Full-HD resolution or 3600kbps.

TODO: Explain other options

## Organize

## Scheduling

```bash
~/.config/systemd/user/dl_ruv.service
#
[Unit]
Description=Download content from RÚV

[Service]
Type=simple
ExecStart=/home/haukurpj/Projects/ruv-dl/fetch_all.fish

[Install]
WantedBy=default.target

~/.config/systemd/user/dl_ruv.timer
#
[Unit]
Description=Schedule RÚV content downloading

[Timer]
#Execute job if it missed a run due to machine being off
Persistent=true
OnCalendar=daily
#File describing job to execute
Unit=dl_ruv.service

[Install]
WantedBy=timers.target
```

systemctl --user start dl_ruv
systemctl --user status dl_ruv

systemctl --user start dl_ruv.timer
systemctl --user status dl_ruv.timer

journalctl --user -S today -u dl_ruv
systemctl --user enable dl_ruv.timer

https://opensource.com/article/20/7/systemd-timers
https://fedoramagazine.org/systemd-timers-for-scheduling-tasks/

## Development

Features to be added

- Handling of mp3 downloading.
- Create a main class instead of config class.
- Refactor main class to return objects and refactor cli to turn those objects to some readable format.
- Return a list of donwloaded episodes from download.

Testing required

- Are the subtitles burnt into the mp4 video stream or are they in their own stream?

## Disclaimer

You are not the owner/copyright holder of the content you download and neither am I.
You are not allowed to distribute the content you download.
You are expected to delete the content when it is no longer available on RÚV.
