# Project Title

The Item Catalog project contains the Python files and HTML templates to set up a basic item catalog. An optional Vagrantfile to ensure
users have the same environment as the developer.

## Getting Started

Clone the repository.
Install Vagrant and VirtualBox.

Vagrant - https://www.vagrantup.com/
VirtualBox - https://www.virtualbox.org/wiki/Downloads

### Prerequisites

Have Python 2.7 installed.
Have Vagrant installed.
Have VirtualBox installed.

### Installing

Clone repository into the Vagrant directory that contains the VagrantFile.
Open a command window and navigate to your Vagrant folder.
Type in `vagrant up` in the window to initialize the virtual machine.
Type in `vagrant ssh` to SSH into the virtual machine.
Type in `python database_setup.py` to set up the database.
Run the application by typing in `python catalog.py`

## Built With

Python 2.7
Atom
Git
Vagrant
VirtualBox

## Authors

* **Mason Cheong

## Acknowledgments

Thanks to Udacity for providing the VagrantFile and logic behind the Google sign in.
