# data-flow-monitor

### OVERVIEW

The data-flow monitor is designed to check the SNO+ Grafana page for any issues in transfer efficiency, and report them both
daily and weekly to the processing group.

As of v2.0, the tool no longer relies on scraping as I was able to finally acquire an API key. This allows the tool to run
significantly faster and more reliably as it can simply make a call to the data source and retrieve the result rather than
running through all of the webpages.

### REQUIREMENTS

* virtualenv (in order to install the isolated python environment)

### INSTALLATION

1. Download the release directory
2. Modify run_script.sh to ensure it changes into the correct install directory so that Cron can see the contents.
3. Add execute permissions to run_script.sh (chmod +x run_script.sh)
4. Ensure you have the grafana API token stored somewhere and modify run_script.sh to pass in the path to it when running 
   data_processor.py
5. (OPTIONAL) Schedule as a Cron job so that it runs on a schedule.

### TO RUN

`./run_script`

### NOTE

Currently, our Grafana is posting data one hour behind (ex. if it is 14:23, then it should post 14:00 as the latest but it posts 13:00) so there is a line in the data_processor.py to account for this. This is potentially by design from whoever set up our dashboard, so this may need to be modified depending on how **yours** is set up and will probably become an option in the config soon.

### CREDITS

[Jamie Rajewski](https://github.com/jamierajewski) <jrajewsk@ualberta.ca>
