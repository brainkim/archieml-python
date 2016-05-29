# ArchieML

Parse Archie Markup Language (ArchieML) documents into Python data structures.

Read about the ArchieML specification at [archieml.org](http://archieml.org).

<!-- I wonder if this will help help SEO (`v0.1.0`, was being distributed instead) -->
The current version is `v0.3.0`.

## Installation [(with pip)](https://pypi.python.org/pypi/archieml/0.3.0)

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
