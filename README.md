# tomato: au-tomation without pain!

[![Documentation](https://badgen.net/badge/docs/dgbowl.github.io/grey?icon=firefox)](https://dgbowl.github.io/tomato)
[![PyPi version](https://badgen.net/pypi/v/dgpost/?icon=pypi)](https://pypi.org/project/tomato)
![Github link](https://badgen.net/github/tag/dgbowl/tomato/?icon=github)
![Github status](https://badgen.net/github/checks/dgbowl/tomato/?icon=github)

`tomato` is the instrument automation package developed at Empa. Windows-only. 
Currently supported hardware is:

- a Dummy device for testing
- BioLogic potentiostats via the EC-Lib library

See the [Documentation](https://dgbowl.github.io/tomato) for more detailed info.

## Usage

The `tomato` package consists of two key parts: the job scheduler app `tomato`,
and the queue management app `ketchup`.

### `tomato`

The job scheduler `tomato` can be started in verbose mode for diagnostic output:

    tomato -vv

`tomato` is used to schedule *jobs* from the *queue* onto *pipelines*. A *pipeline*
is a way of organising one or many *devices* in a single, addressable unit. In general, 
a single *pipeline* should be a digital twin composed of all *devices* neccessary to
carry out a single *payload*.

Note that only a single instance of `tomato` can be running at a single machine.
    
### `ketchup`

`ketchup` is used to submit, check the status of, and cancel *jobs* to the *queue*,
as well as to load or eject *samples* from *pipelines*.

To submit a *payload* to the *queue*, run:

    ketchup submit <payload.yml>

where `<payload.yml>` is a file containing the *payload* information, including
the description of the *sample*, details of the *method*, and other information
required by `tomato`.

To check the status of the *queue* or of a *job*, run either of:

    ketchup status
    ketchup status queue
    ketchup status <jobid>

The first option will print information about the status of all *pipelines*
that `tomato` is managing. The second option, with the `queue` argument, will
print information about all jobs that are currently in the *queue* or already
running - information about completed jobs is not currently shown. Finally,
to check the status of a single *job*, supply the `<jobid>` as an argument.

## Output data

By default, all data in the *job* folder is processed using `yadg` to create
a *datagram*, and zipped into a zip archive. This zip archive includes all raw
data files, the `tomato_job` log file, and a copy of the full job payload in a 
`json` file. The *datagram* contains timestamped, unit-annotated raw data, and
included instrumental uncertainties.

The default location where this output will be placed is the `cwd` where the 
`ketchup submit` was executed; the default filenames of the returned files are
`results.<jobid>.[zip,json]`.

## Contributors:
- [Peter Kraus](http://github.com/PeterKraus)