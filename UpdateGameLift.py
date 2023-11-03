import getopt
import json
import subprocess
import sys
import time

def main(argv):
    try:
        callAwsCli(["--version"])
    except:
        logError("Issue calling AWS cli")
        sys.exit(2)

    try:
        opts, args = getopt.getopt(
            argv, "", ["alias_id=", "fleet_id=", "monitoring_interval=", "timeout="]
        )
    except getopt.GetoptError:
        logError("Incorrect arguments passed to script")
        sys.exit(2)


    # Required args
    alias_id = None
    fleet_id = None

    # Optional args
    monitoring_interval = 60
    timeout = 3600  # 1 hour

    for opt, arg in opts:
        if opt == "--alias_id":
            alias_id = arg
        elif opt == "--fleet_id":
            fleet_id = arg
        elif opt == "--monitoring_interval":
            monitoring_interval = int(arg)
        elif opt == "--timeout":
            timeout = int(arg)


    checkRequiredArgs(alias_id = alias_id, fleet_id = fleet_id)

    logInfo(f"Fleet: {fleet_id}")
    logInfo(f"Alias: {alias_id}")
    log("=====================================")

    total_polling_time = 0

    while not fleetReadyOrFailed(fleet_id):
        if total_polling_time > timeout:
            logError("Fleet status monitoring timeout. Exiting...")
            sys.exit(2)

        logInfo(f"Sleeping for {monitoring_interval} seconds")
        time.sleep(monitoring_interval)
        total_polling_time += monitoring_interval
        logInfo(f"{timeout - total_polling_time} seconds until timeout")

    updateAlias(alias_id, fleet_id)


def fleetReadyOrFailed(fleet_id):
    location_attributes_json = callAwsCli(
        ["gamelift", "describe-fleet-location-attributes", "--fleet-id", fleet_id], True
    )

    attributes = location_attributes_json["LocationAttributes"]

    error_in_region = False
    active_regions = 0
    total_regions = len(attributes)

    for attribute in attributes:
        location_state = attribute["LocationState"]
        location = location_state["Location"]
        status = location_state["Status"]

        logInfo(f"Location: {location} Status: {status}")
        if status == "ERROR":
            error_in_region = True

        if status == "ACTIVE":
            active_regions += 1

    if error_in_region:
        logError("Fleet activation error!!!")
        sys.exit(2)

    log("=====================================")

    return active_regions == total_regions


def updateAlias(alias_id, fleet_id):
    routing_strategy = json.dumps({"Type": "SIMPLE", "FleetId": fleet_id})

    args = [
        "gamelift",
        "update-alias",
        "--alias-id",
        alias_id,
        "--routing-strategy",
        routing_strategy,
    ]

    result = callAwsCli(args, True)
    logInfo(f"Alias updated: {result}")


def callAwsCli(args, full_json=False):
    aws_call = ["aws"] + args
    logInfo(f"AWS cli call: {subprocess.list2cmdline(aws_call)}")

    result = subprocess.run(aws_call, capture_output=True, text=True)

    if result.returncode == 0:
        if not full_json:
            output_lines = result.stdout.strip().split("\n")
            return output_lines[-1]
        else:
            return json.loads(result.stdout.strip())
    else:
        raise Exception(
            f"AWS command failed with error code {result.returncode}: {result.stderr.strip()}"
        )

def checkRequiredArgs(**kwargs):
    logInfo(f"Checking required arguments: {kwargs.items()}")
    for key, value in kwargs.items():
        if(value is None):
            logError(f'{key} is a required argument and was not provided. Exiting...')
            sys.exit(2)

def log(msg):
    print(msg)

def logInfo(msg):
    print("INFO: " + msg)

def logWarning(msg):
    print("WARNING: " + msg)

def logError(msg):
    print("ERROR: " + msg)

if __name__ == "__main__":
    main(sys.argv[1:])
