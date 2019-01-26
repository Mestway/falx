# Falx

copy paste to make visualization design easier

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

- Install python dependencies:

   ```pip install -r requirements.txt```

- Install falx in the development mode to resolve dependencies
  
  ```pip install -e .```

- Install the Tyrell framework and its dependencies:

  - Obtain a tarball distribution of tyrell. Suppose the name of the tarball is ``tyrell-0.1.tar.gz``:

   ```pip install tyrell-0.1.tar.gz```

   (Note: One of Tyrell's dependency, `z3-solver`, takes a long time to build. Please be patient.)

  - To test Tyrell installation, run the following command:

     ```parse-tyrell-spec --help```

    If the help message is correctly shown, tyrell is properly installed.

  - Install R 3.3+ and its relevant libraries for data wrangling （https://cran.r-project.org/bin/macosx/R-3.5.2.pkg）
      - dplyr: install.packages("dplyr", dependencies=TRUE)
      - tidyr: install.packages("tidyr", dependencies=TRUE)
      - jsonlite: install.packages("jsonlite", dependencies=TRUE)

## Run

To run the Falx design synthesizer:

```cd falx; python run.py```

To test Tyrell enumerator:

```cd falx; python morpheus_enumerator.py```
