from genericpath import isfile
import os
import subprocess
import sys, getopt
import json
import time

# Global variables
PROJECT_NAME = "GameLiftTutorial"

def main(argv):
    try:
        callAwsCli(["--version"])
    except:
        logError("Issue calling AWS cli")
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv, "", ["build_name=", "build_version=", "build_path=", "build_sdk_version=", "fleet_name=", "aws_region="])
    except getopt.GetoptError:
        logError("Incorrect arguments passed to script")
        sys.exit(2)

    # Required args
    build_name = None
    build_version = None
    build_path = None
    build_sdk_version = None
    fleet_name = None
    aws_region = None

    for opt, arg in opts:
        match opt:
            case "--build_name":
                build_name = arg
            case "--build_version":
                build_version = arg
            case "--build_path":
                build_path = arg
            case "--build_sdk_version":
                build_sdk_version = arg
            case "--fleet_name":
                fleet_name = arg
            case "--aws_region":
                aws_region = arg
    
    checkRequiredArgs(
        build_name = build_name,
        build_version = build_version,
        build_path = build_path,
        build_sdk_version = build_sdk_version,
        fleet_name = fleet_name,
        aws_region = aws_region
    )

    launch_path = gatherLaunchPath(PROJECT_NAME, build_path)
    logInfo(f"Launch path: {launch_path}")

    build_id = uploadBuild(build_name, build_version, build_path, aws_region, build_sdk_version)
    logInfo("Uploaded Build to GameLift: " + build_id)

    while not buildReadyOrFailed(build_id):
        logInfo("Waiting for Build to be Ready. Sleeping for 1 second")
        time.sleep(1)

    

    fleet_id = createFleet(
        fleet_name, build_id, launch_path, PROJECT_NAME, "production"
    )

    saveResultToFile(fleet_id)


def gatherLaunchPath(project_name, build_path):
    launch_path_start = r"{}\Binaries\Win64".format(project_name)
    exe_path = os.path.join(build_path, launch_path_start)
    files = os.listdir(exe_path)
    exe_files = [file for file in files if file.endswith(".exe")]
    executable_name = os.path.splitext(exe_files[0])[0]

    return r"{}\{}.exe".format(launch_path_start, executable_name)

def saveResultToFile(result):
    filename = "fleetId.txt"
    with open(filename, "w") as file:
        file.write(result)




def uploadBuild(name, version, path, region, sdk_version):
    result = callAwsCli(
        [
            "gamelift",
            "upload-build",
            "--name",
            name,
            "--build-version",
            version,
            "--build-root",
            path,
            "--region",
            region,
            "--operating-system",
            "WINDOWS_2016",
            "--server-sdk-version",
            sdk_version
        ]
    )
    id = extractBuildId(result)
    return id


def extractBuildId(output):
    parts = output.split(":")
    return parts[1].strip()


def buildReadyOrFailed(build_id):
    json = callAwsCli(["gamelift", "describe-build", "--build-id", build_id], True)
    status = json["Build"]["Status"]

    if status == "ERROR":
        logError("Build Uploaded with status: ERROR")
        sys.exit(2)

    return status == "READY"


def createFleet(name, build_id, launch_path, project_name, environment):
    instance_type = "c4.large"
    fleet_type = "SPOT"
    description = f"Fleet {name} from build {build_id} created from Jenkins"
    ports = json.dumps(
        [
            {
                "FromPort": 7777,
                "ToPort": 8000,
                "IpRange": "0.0.0.0/0",
                "Protocol": "UDP",
            }
        ]
    )
    runtime_configuration = json.dumps(
        {
            "ServerProcesses": [
                {
                    "LaunchPath": r"C:\game\{}".format(launch_path),
                    "ConcurrentExecutions": 3,
                }
            ],
            "GameSessionActivationTimeoutSeconds": 600,
        }
    )
    locations = json.dumps(
        [
            {"Location": "eu-west-1"},
            {"Location": "us-west-1"},
            {"Location": "us-east-1"}
        ]
    )
    tags = json.dumps(
        [
            {"Key": "dev", "Value": "Jenkins"},
            {"Key": "game", "Value": project_name},
            {"Key": "env", "Value": environment},
            {"Key": "project", "Value": "UE5 CI/CD"}
        ]
    )
    result = callAwsCli(
        [
            "gamelift",
            "create-fleet",
            "--name",
            name,
            "--description",
            description,
            "--build-id",
            build_id,
            "--locations",
            locations,
            "--tags",
            tags,
            "--ec2-instance-type",
            instance_type,
            "--fleet-type",
            fleet_type,
            "--ec2-inbound-permissions",
            ports,
            "--runtime-configuration",
            runtime_configuration,
        ],
        True,
    )

    logInfo(f"Created Fleet: {result}")
    
    return str(result["FleetAttributes"]["FleetId"]);


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
