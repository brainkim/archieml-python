# ArchieML

Parse Archie Markup Language (ArchieML) documents into Python data structures.

Read about the ArchieML specification at [archieml.org](http://archieml.org).

<!-- I wonder if this will help help SEO (`v0.1.0`, was being distributed instead) -->
## Installation [(with pip)](https://pypi.python.org/pypi/archieml/0.3.4)
The current version is `==0.3.4` (hopefully, you never know).

`pip install archieml`

## Usage

```python
import archieml

# use archieml.load to load data from a file
with open('a.aml') as f:
    data = archieml.load(f)

# or use archieml.loads to load data from a string

data = archieml.loads("""

key: value
[array]
* 1
* 2
* 3

""")
```

## Contributing

We pull test fixtures from the ArchieML repository (https://github.com/newsdev/archieml.org). This is done using git submodules for some reason. Run the following command to pull the repository.

```shell
git submodule update --init
```

Then, run the following command to run unit tests.

```shell
./setup.py test
```
