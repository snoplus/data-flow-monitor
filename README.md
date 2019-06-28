# data-flow-monitor

### OVERVIEW

The data-flow-monitor was designed as a way to scrape data from the "Efficiency" view on a Grafana dashboard where the user does NOT have access to the API (when you only have a viewer account). The strategy implemented here can be utilized elsewhere as it uses general webscraping methodologies.

### REQUIREMENTS

* virtualenv (in order to install the isolated python environment)
* Singularity (3.1+ recommended, otherwise there may be issues with passing environment variables into the container)

### INSTALLATION

1. Download the release directory
2. Modify run_script.sh to ensure it changes into the correct install directory so that Cron can see the contents.
3. Add execute permissions to run_script.sh (chmod +x run_script.sh)
4. Modify grafana_config.json accordingly if credentials are necessary.
5. Modify processor_config.json accordingly (NOT IMPLEMENTED YET; manual changes need to be made to both grafana-automation.js AND data_processor.py depending on your usage scenario).
6. (OPTIONAL) Schedule as a Cron job.

### NOTE

Currently, our Grafana is posting data one hour behind (ex. if it is 14:23, then it should post 14:00 as the latest but it posts 13:00) so there is a line in the data_processor.py to account for this. This is potentially by design from whoever set up our dashboard, so this may need to be modified depending on how **yours** is set up and will probably become an option in the config soon.

### CREDITS

[Jamie Rajewski](https://github.com/jamierajewski) <jrajewsk@ualberta.ca>
