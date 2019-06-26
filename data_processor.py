# Data processor for retrieved Grafana Efficiency Data
# By Jamie Rajewski <jrajewsk@ualberta.ca>

import json
import subprocess
import numpy
from datetime import datetime
from datetime import timedelta
import time

# These are the thresholds to check for. If the
# values have been consecutively below EFFICIENCY_THRESHOLD
# for HOUR_THRESHOLD, add to the report
HOUR_THRESHOLD = 3
EFFICIENCY_THRESHOLD = 0.90
# The mean threshold is what the mean of the HOUR_THRESHOLD interval should be at or above,
# otherwise add to the report
MEAN_THRESHOLD = 0.75
# Use this when computing the mean
MEAN_HOUR_THRESHOLD = 6

# Send email alerts to these emails, separated by commas
email_list = ""


# These are the dst_hostnames. This list is used to figure out which are missing, if any, and correspond to the option "dst_hostnames" in the "Group By" filter
hostnames = ["fndca4a.fnal.gov", "lcg-se1.sfu.computecanada.ca", "srm-snoplus.gridpp.rl.ac.uk"]

# Create a global report string that can be appended to throughout processing as any issues are found;
# At the end, if the report isn't empty, send it out
issue_report = ""

# Opens a JSON data file and parses it down.
# Returns a dict with the dst_hostname as key and the list of [time, value] pairs as the value
def parse_data(data):
    global issue_report
    final_dict = {}
    f = open(data, "r")

    if f.mode == "r":
        data_json = f.read()
        data_dict = json.loads(data_json)

        # Iterate through the 3 dst_hostnames
        number_of_hosts = len(data_dict["results"][0]["series"])

        for i in range(number_of_hosts):
            dst_hostname = data_dict["results"][0]["series"][i]["tags"]["dst_hostname"]
            dst_hostname = dst_hostname.strip()

            # Remove each found hostname from the known list to narrow down the missing ones, if any
            hostnames.remove(dst_hostname)

            data = data_dict["results"][0]["series"][i]["values"]
            final_dict[dst_hostname] = data

        # Add any remaining hosts to the report as missing hostnames (meaning they are completely missing)
        # If it is empty, this loop will simply be skipped
        for host in hostnames:
            missing = "---MISSING dst_hostname---\n{} is missing altogether from the last 12 hours of data\n\n".format(host)
            issue_report += missing

        return final_dict


# Take the [[time, eff], [time, eff]...] list and calculate
# stats from it
def calculate_stats(data_list, host):
    global issue_report

    # Take the list of pairs and pull out just the efficiency data
    eff_list = map(lambda x: x[1], data_list)
    # Now create a numpy-compatible array
    eff_array = numpy.array(eff_list)

    # Now calculate the standard deviation
    stddev = numpy.std(eff_array)

    # And get the mean
    mean = numpy.mean(eff_array)

    ## NOTE - Extra statistics, just in case ##
    # print "Mean and Std. Dev. for {}: {}, {}".format(host, mean, stddev)
    # print "Standard error: ", (stddev / numpy.sqrt(len(eff_list)))

    # If the mean is below the 
    if mean < MEAN_THRESHOLD:
        under_mean = "---UNDER MEAN THRESHOLD---\nThe calculated mean of {} is below the threshold of {} for {}\n\n".format(mean, MEAN_THRESHOLD, host)
        issue_report += under_mean


# Check if the number of points is at least as many as HOUR_THRESHOLD (since we want more points for the mean than for checking efficiency);
# if not, add it to the report
# Returns a corrected data list with all gaps filled
def check_number_of_points(data_list, host):
    global issue_report

    # Create a new list and store the required values for gathering statistics in there.
    # This will preserve the original
    new_list = []
    to_insert = datetime.now()

    ## NOTE ##
    # Grafana appears to upload the previous hour,
    # meaning the latest data point will be (now - 1) so account for
    # that; I don't think this is regular behaviour as
    # I have seen it upload the current hour so adjust as required
    to_insert -= timedelta(hours=1)

    count = 0
    for i, e in reversed(list(enumerate(data_list))):

        count += 1
        current = datetime.fromtimestamp(e[0]/1000)

        change = to_insert - current
        change = int(change.total_seconds() // 3600)
        
        # If there is a gap in the data, and that gap is within our
        # MEAN_HOUR_THRESHOLD, report on it
        if change > 0 and count <= MEAN_HOUR_THRESHOLD:

            missing_points = "---MISSING POINTS---\n{} has a gap of {} hours between {} and {}\n\n".format(host, change, to_insert.strftime("%x %H:00"), current.strftime("%x %H:00"))
            issue_report += missing_points

        # If the difference between times is an hour or more
        for hour in range(change):

            unix_time = int(to_insert.strftime("%s")) * 1000
            new_list.insert(0, [unix_time, 0])

            to_insert -= timedelta(hours=1)

        # Now that preceding missing values have been inserted, put
        # back the original value
        new_list.insert(0, e)

        # Move to_insert to next hour
        to_insert -= timedelta(hours=1)

    # Now that we have added in missing data in between, check if we have at least HOUR_THRESHOLD points.
    # If not, then we need to add more zero's on the end (since we should have had that many points to start)
    if len(new_list) < MEAN_HOUR_THRESHOLD:
        
        # If there are fewer than the threshold worth of data points, record it in the report
        missing_points = "---MISSING POINTS---\n{} only has {} of the {} mean-hour threshold of data; adding additional points with 0's\n\n".format(host, len(data_list), MEAN_HOUR_THRESHOLD)
        issue_report += missing_points

        missing = MEAN_HOUR_THRESHOLD - len(new_list)

        # The time doesnt really matter at this point so just add in zero to simplify
        for point in range(missing):
            new_list.insert(0, [0, 0])

    # After the processing is complete, we should now have a consistent list of data, so take just the last MEAN_HOUR_THRESHOLD
    # worth of points and calculate the stats from it
    calculate_stats(new_list[-MEAN_HOUR_THRESHOLD:], host)

    return new_list


# Checks if the latest (fixed) data is consecutively under EFFICIENCY_THRESHOLD
# for HOUR_THRESHOLD
def check_consecutive_efficiency(data_list, key):
    global issue_report

    # Use a count to keep track of how many we've checked since the reversed method keeps
    # original indices intact
    count = 0
    hours_under = 0
    for value in reversed(data_list):

        if value[1] < EFFICIENCY_THRESHOLD:
            hours_under += 1

        if hours_under >= HOUR_THRESHOLD:
            # Add to report, then end
            under_issue = "---UNDER EFFICIENCY THRESHOLD---\n{} has been under the efficiency threshold of {} for {} hours\n\n".format(key, EFFICIENCY_THRESHOLD, hours_under)
            issue_report += under_issue
            return

        count += 1
        # If we haven't exceeded the HOUR_THRESHOLD consecutively in the latest data,
        # return without adding to report
        if count >= HOUR_THRESHOLD:
            return


# Iterates through [time, efficiency] pairs and
# checks for any lengthy drops in efficiency
# among each of the dst_hostnames
def process_data(data_dict):

    global issue_report

    # Iterate over dst_hostnames (there may be less than the expected 3 but
    # this was taken care of in the parse stage)
    for key in data_dict:

        # Keep track of how many consecutive hours efficiency has been below the threshold
        hours_under = 0

        # First, check if there are actually any points available
        if len(data_dict[key]) == 0:
            no_points = "No points available for host {}\n\n".format(key)
            issue_report += no_points
            continue

        # Check the number of available data points
        fixed_list = check_number_of_points(data_dict[key], key)
        
        # Check the latest data points for consecutive efficiency issues
        check_consecutive_efficiency(fixed_list, key)


def send_report():
    global issue_report
    global email_list

    timestamp = datetime.now().strftime("%x %X")
    # Add in the header
    issue_report = "\n\n[\tAutomated Grafana Issue Report - " + timestamp + "\t]\n\tProblematic data attached to this email;\n\tReport any bugs/questions/suggestions to <jrajewsk@ualberta.ca>\n\n" + issue_report
    issue_report += "[\t\t---END OF REPORT---\t\t]"
    
    # This print is to be stored in a log with cron, so if that is
    # unnecessary then comment it out
    print issue_report

    cmd = "echo -e '{}' | mailx -a data.json -s 'Automated Grafana Issue Report' {}".format(issue_report, email_list)
    subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)


# Same as main but accepts a parameter for the data file to ease testing
def tester(datafile):
    data_dict = parse_data(datafile)

    process_data(data_dict)

    if issue_report != "":
        send_report()


# Open the data file and check to see if there were any errors encountered during the
# retrieval stage. If so, add an issue to the report and end here since data retrieval
# failed
def check_retrieval_errors(data_file):
    issue = ""
    with open(data_file) as f:
        data = f.read()
        split = data.split("-")

        if split[0] == "error":
            issue = split[1]
    return issue
    

def main():
    global issue_report
    # This is the name of the data file. Hard-coded as data.json since
    # that's what the grafana-scraper tool provides but can be changed for testing
    data_file = "data.json"

    # First, check to ensure we haven't received any errors in the data retrieval step.
    # If we did, then add it to the issue report and send, then terminate
    issue = check_retrieval_errors(data_file)
    if issue != "":
        issue_report = issue + "\n\n"
        send_report()
        return

    # Parse the data into a dictionary while performing
    # preliminary checks
    # data_dict -> Key: dst_hostname, Value: [time, value]
    data_dict = parse_data(data_file)
    
    process_data(data_dict)

    # If issue_report isn't empty, it means we have an issue to send so send it out
    if issue_report != "":
        send_report()
    

if __name__ == "__main__":
    main()
