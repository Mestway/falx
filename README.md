# Falx

copy paste to make visualization design easier

## Instructions

Install dependencies: run `pip install -r requirements.txt`.

Install falx in the development mode: `pip install -e .`, this is necessary to resolve dependencies.


First of all, make sure that your system has a python version >=3.6 installed.

It is recommended that a `virtual environment <https://docs.python.org/3/library/venv.html>`_ is used when starting with a new project:

   $ mkdir venv
   
   $ python3 -m venv ./venv
   
   $ source venv/bin/activate

Now, you may install the Tyrell framework and its dependencies.


- Obtaining a tarball distribution of tyrell. Suppose the name of the tarball is ``tyrell-0.1.tar.gz``:

   $ pip install tyrell-0.1.tar.gz

.. note:: One of Tyrell's dependency, `z3-solver`, takes a long time to build. Please be patient.

To test whether the installation is successful, run the following command:

   $ parse-tyrell-spec --help

If the help message is correctly shown, everything should be good.

- Install R 3.3+ and its relevant libraries for data wrangling （https://cran.r-project.org/bin/macosx/R-3.5.2.pkg）
    - dplyr: install.packages("dplyr", dependencies=TRUE)
    - tidyr: install.packages("tidyr", dependencies=TRUE)


- Try our toy example:

   $ cd falx; python morpheus_enumerator.py
