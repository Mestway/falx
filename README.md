# Falx

An opportunistic programming tool for visualizations to make design easier.

## Set up

Requirement: Python version >=3.7.

#### Create virtual environment (recommended)


[Virtual Environment](<https://docs.python.org/3/library/venv.html>) or [Conda](https://www.anaconda.com/download/#macos) is recommended for managing dependencies:

If using Virtual Environment:

   ```
   mkdir venv
   python3 -m venv ./venv
   source venv/bin/activate
   ```
   
If using Conda:

   ```
   conda create -n falx python=3.7 anaconda
   source activate falx
   ```
   
At development time, use `source venv/bin/activate` (venv) or `source activate falx` (conda) to activate the virtual environment.

#### Install dependencies

1. Install python dependencies: `pip install -r requirements.txt`

2. Install falx in the development mode: `pip install -e .`

3. Install Tyrell and dependencies:

   * Obtain a tarball distribution of tyrell and run `pip install tyrell-0.1.tar.gz`

   * To test Tyrell installation, run: `parse-tyrell-spec --help` (it is properly installed if help messages show up).

   * Install [R 3.3+](https://cran.r-project.org/bin/macosx/R-3.5.2.pkg) and the following data wrangling libraries:
       - dplyr: `install.packages("dplyr", dependencies=TRUE)`
       - tidyr: `install.packages("tidyr", dependencies=TRUE)`
       - jsonlite: `install.packages("jsonlite", dependencies=TRUE)`
       - jsonlite: `install.packages("compare", dependencies=TRUE)`

## Run

To run the Falx design synthesizer: `cd falx; python run.py`

To test Tyrell enumerator: `cd falx; python morpheus.py`
