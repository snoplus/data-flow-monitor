# Data processor for retrieved Grafana Efficiency Data
# By Jamie Rajewski <jrajewsk@ualberta.ca>

import json
import subprocess
import numpy
import requests
import sys
from datetime import datetime
from datetime import timedelta
from os import system
from os import path
from os import remove
from time import sleep


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
email_list = "snoplus_vosupport@snolab.ca"

# These are the dst_hostnames. This list is used to figure out which are missing, if any, and correspond to the option "dst_hostnames" in the "Group By" filter
hostnames = ["fndca4a.fnal.gov", "lcg-snopse1.sfu.computecanada.ca", "srm-snoplus.gridpp.rl.ac.uk"]

# Create a global report string that can be appended to throughout processing as any issues are found;
# At the end, if the report isn't empty, send it out
issue_report = ""

# Similar to the above, but for the weekly report
weekly_report = ""

# Fetch the efficiency data from Grafana
# The Grafana API token should be stored in the same directory as this file,
# in a file called token.txt
def fetch_data(timeframe):
    global issue_report

    period = ""
    if timeframe == "week":
        period = "7d"
    elif timeframe == "day":
        period = "12h"
    else:
        print "Incorrect time period specified, exiting..."
        sys.exit(1)
    
    token = ""
    with open("token.txt", "r") as the_file:
        token = (the_file.readline()).strip('\n')
        
    auth = "Bearer {}".format(token)
    headers = {'Authorization': auth}
    query = '''SELECT mean("efficiency") FROM "one_month"."transfer_fts_efficiency" WHERE ("vo" =~ /^snoplus\.snolab\.ca$/ AND "src_country" =~ /^.*$/ AND "src_site" =~ /^.*$/ AND "dst_country" =~ /^.*$/ AND "dst_site" =~ /^.*$/ AND "endpnt" =~ /^.*$/) AND time >= now() - {} GROUP BY time(1h), "dst_hostname" fill(none)'''.format(period)
    datasourceid = "7794"
    url = "https://monit-grafana.cern.ch/api/datasources/proxy/{}/query?db=monit_production_transfer&q={}".format(datasourceid,query)

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        return r.text

    else:
        failed_request = "---FAILED REQUEST---\nThe request to retrieve the efficiency data from Grafana failed with HTTP status {}\n\n".format(r.status_code)
        issue_report += failed_request

        
# Opens a JSON data file and parses it down.
# Returns a dict with the dst_hostname as key and the list of [time, value] pairs as the value
def parse_data(data):
    global issue_report
    final_dict = {}

    data_dict = json.loads(data)

    # Iterate through the 3 dst_hostnames
    number_of_hosts = len(data_dict["results"][0]["series"])

    for i in range(number_of_hosts):
        dst_hostname = data_dict["results"][0]["series"][i]["tags"]["dst_hostname"]
        dst_hostname = dst_hostname.strip()

        # Remove each found hostname from the known list to narrow down the missing ones, if any
        if dst_hostname in hostnames:
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


# Compute the weekly average efficiency and downtime for the weekly report
def calculate_stats_weekly(data_dict):
    global weekly_report

    # Pull each individual list and combine them
    for key in data_dict:
        
        # Fill in any gaps that exist with 0's
        fixed = fill_gaps(data_dict[key], "NONE")

        # Get just the efficiencies
        eff_list = map(lambda x: x[1], fixed)
        
        # Now create a numpy array
        eff_array = numpy.array(eff_list)
        
        # Get the mean
        mean = numpy.mean(eff_array) * 100

        # We're done with the mean now, so get the downtime
        downtime = (float(eff_list.count(0)) / float(len(eff_list))) * 100
        
        weekly_report += "---{}---\n".format(key)
        weekly_report += "Average efficiency over the last week: {}%\n\n".format(mean)
        weekly_report += "Downtime over the last week: {} hours, or {}% of the time\n\n".format(eff_list.count(0),downtime)


# Take the data_list, and fill in any gaps in time where there was no value
# with a 0
def fill_gaps(data_list, host):
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
        current = datetime.strptime(e[0], "%Y-%m-%dT%H:%M:%SZ")
        change = to_insert - current
        change = int(change.total_seconds() // 3600)
        
        # If there is a gap in the data, and that gap is within our
        # MEAN_HOUR_THRESHOLD, report on it
        if change > 0 and count <= MEAN_HOUR_THRESHOLD:

            missing_points = "---MISSING POINTS---\n{} has a gap of {} hours between {} and {}\n\n".format(host, change, to_insert.strftime("%x %H:00"), current.strftime("%x %H:00"))
            issue_report += missing_points

        # If the difference between times is an hour or more
        for hour in range(change):

            unix_time = to_insert.strftime("%Y-%m-%dT%H:%M:%SZ")
            new_list.insert(0, [unix_time, 0])

            to_insert -= timedelta(hours=1)

        # Now that preceding missing values have been inserted, put
        # back the original value
        new_list.insert(0, e)

        # Move to_insert to next hour
        to_insert -= timedelta(hours=1)
    
    return new_list


# Check if the number of points is at least as many as HOUR_THRESHOLD (since we want more points for the mean than for checking efficiency);
# if not, add it to the report
# Returns a corrected data list with all gaps filled
def check_number_of_points(data_list, host):
    global issue_report

    new_list = fill_gaps(data_list, host)

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


def send_report(data):
    global issue_report
    global email_list
    
    timestamp = datetime.now().strftime("%x %X")
    # Add in the header
    issue_report = "\n\n[\tAutomated Grafana Issue Report - " + timestamp + "\t]\n\tProblematic data attached to this email;\n\tReport any bugs/questions/suggestions to <jrajewsk@ualberta.ca>\n\n" + issue_report
    issue_report += "[\t\t---END OF REPORT---\t\t]"
    
    # This print is to be stored in a log with cron, so if that is
    # unnecessary then comment it out
    print issue_report

    # Write the data to a file and attach it to the email
    with open("data.json", "w") as the_file:
        the_file.write(data)
        
    if path.exists("data.json"):
        cmd = """echo "{b}" | mailx -a "{f}" -s "{s}" "{to}" 2>/dev/null""".format(b=issue_report, f="data.json", s="Automated Grafana Issue Report", to=email_list)
        system(cmd)
        

def send_weekly_report(data):
    global email_list
    global weekly_report

    timestamp = datetime.now().strftime("%x %X")
    # Add in the header
    weekly_report = "\n\n[\tAutomated Grafana Weekly Report - " + timestamp + "\t]\n\tReport any bugs/questions/suggestions to <jrajewsk@ualberta.ca>\n\n" + weekly_report
    weekly_report += "[\t\t---END OF REPORT---\t\t]"
    
    # This print is to be stored in a log with cron, so if that is
    # unnecessary then comment it out
    print weekly_report

    with open("weekly-data.json", "w") as the_file:
        the_file.write(data)

    cmd = """echo "{b}" | mailx -a "{f}" -s "{s}" "{to}" 2>/dev/null""".format(b=weekly_report, f="weekly-data.json", s="Automated Grafana Weekly Report", to=email_list)
    system(cmd)

    
def main():
    global issue_report
    global weekly_report
    
    # First, fetch the data from Grafana
    data_file = fetch_data("day")
    
    # First, check to ensure we haven't received any errors in the data retrieval step.
    # If we did, send the report
    if issue_report != "":
        send_report(data_file)
        sys.exit(1)
    
    # Parse the data into a dictionary while performing
    # preliminary checks
    # data_dict -> Key: dst_hostname, Value: [time, value]
    data_dict = parse_data(data_file)        
    process_data(data_dict)

    # Do one final check if the issue report has anything to send
    if issue_report != "":
        send_report(data_file)
    
    # Now, check if there is any weekly data available (meaning it's time to send a report)
    if datetime.today().weekday() == 1 and datetime.now().hour >= 3 and datetime.now().hour <= 4:

        # Send a request for weekly data
        weekly_file = fetch_data("week")
        
        data_dict = parse_data(weekly_file)
        calculate_stats_weekly(data_dict)

        # Send the report
        send_weekly_report(weekly_file)


if __name__ == "__main__":
    main()
