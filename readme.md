# Spinnaker automation test for azure based on citest

## Dependences

 * [citest](https://github.com/google/citest/)
 * [azure cli](https://docs.microsoft.com/cli/azure/install-azure-cli)
 * [azure SDK for python](https://docs.microsoft.com/en-us/azure/python/python-sdk-azure-install)

## Setup

0. Setup Local Git [Spinnaker](https://www.spinnaker.io/setup/) and packer, also prepare a Virtual Network with at least 2 Subnet and a Storage Account with a container named `spinnakertestinglogs` to storage log files in Azure. Note: Storage Account is different from the Spinnaker used.

1. Install [azure cli](https://docs.microsoft.com/cli/azure/install-azure-cli).

2.  Recommend using [Miniconda3](https://docs.conda.io/en/latest/miniconda.html) to manage the python packages, download the Miniconda Linux 64-bit for python3.7 and create your new environment.
    ```
    conda create -n spin python
    conda activate spin
    ```

    Then install [citest](https://github.com/google/citest/) and [azure SDK for python](https://docs.microsoft.com/en-us/azure/python/python-sdk-azure-install).
    ```
    git clone https://github.com/google/citest.git
    cd citest
    pip install -r requirements.txt
    pip install azure
    ```
    
    Here we need to do some modification to avoid errers in citest module, please refer to Modifications setion below.

3. Clone this repo to your machine:
    ```
    cd ~/
    mkdir software
    cd software/
    git clone git@github.com:hund030/spinnakerTestUnit.git
    ```
    Remember to change the PATH setting if you prefer to put this repo in a different directory.
    
4. Fill in your setting/account/key in below files:
    * azure_config.json
    * mail.py
    * uploadLog.py
    * task.sh
    
5. Edit crontab schedule with below command and add your schedule to the bottom.
    ```
    crontab -e
    ```
   Below example schedule 3 jobs, 1st to deploy Spinnaker everyday at 10:00 AM GMT, 2nd to activate miniconda environment and start test tasks 10 minutes after Spinnaker deployment, and 3rd to remove the daemon log files to save disk space on every Sunday.
    ```
    # spinnaker daily test
    0 10 * * * /usr/local/bin/hal deploy apply > /dev/null 2>&1
    10 10 * * * bash -c 'source ~/miniconda3/bin/activate spin && cd ~/software/spinnakerTestUnit/ && bash task.sh'
    0 0 * * 7 rm -rf ~/.gradle/daemon/*
    ```
6. Wait until the test ends and check your email box.

## Modifications
    
 * In [citest\citest\gcp_testing\gcloud_agent.py](), method pty_fork_ssh() and remote_command(), and also in [citest\citest\gcp_testing\gce_util.py](), establish_network_connectivity(), line 290, change argument async=False/True into asyn=False/True
  
 * We don't need google cloud, so delete [spinnaker_testing/gcs_pubsub_trigger_agent.py]() and [spinnaker_testing/google_scenario_support.py] ()and delete relevant code in [spinnaker_testing/\_\_init__.py]() and [spinnaker_testing/spinnaker_test_scenario.py]()

 * In [spinnaker_testing\gate.py](), method _maybe_export_stage_context(), line 132, convert err to string since sometimes err is None which cause string plus None error.
 
 ## Trouble Shooting 
 
* For any failed test case, check the whole process or simply check the error message in your storage account as `uploadLog.py` upload it. Three kinds of files may be uploaded:
    1. *-abstract.log is the content of the email, only containing the status(passed or failed) and duration of each test case.
    2. *.log shows every stage of each test case, and provide a brief error message once a test case failed.
    3. *.html records the whole process for each test case, uploaded only when a test case failed.

* Any error occurs while uploading logs or sending emails will be dump into `daily-running.err` located in your home directory as `task.sh` do so.
