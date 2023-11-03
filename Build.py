import subprocess
import sys, getopt
import os
import time


# Project Constants
PROJECT_NAME = "GameLiftTutorial"
CONFIGURATIONS = ["Debug", "DebugGame", "Development", "Shipping", "Test"]
DEFAULT_PLATFORM = "Win64"
DEFAULT_PARAMS = [
    r"BuildCookRun",
    r"-noP4",
    r"-build",
    r"-cook",
    r"-stage",
    r"-package",
    r"-compile",
    r"-compressed",
    r"-SkipCookingEditorContent",
    r"-pak",
    r"-archive",
    r"-buildmachine",
    r"-NoCodeSign",
    r"-skipdeploy",
    r"-skipbuilderditor",
    r"-nocompileeditor",
    r"-utf8output",
    r"-prereqs",
]

# Logging constants
SEPARATOR = "===================================================="
NEW_LINE = "\n"


def main(argv):
    logStep("Validating Tooling")
    validateTools()

    logStep("Validating Arguments")
    try:
        opts, args = getopt.getopt(
            argv,
            "",
            [
                "pre_reqs",
                "client",
                "server",
                "client_target=",
                "server_target=",
                "configuration=",
                "maps="
            ],
        )

    except getopt.GetoptError:
        logError("Incorrect arguments passed to script")
        sys.exit(2)

    # Required args
    configuration = None

    # Optional args
    pre_reqs = False
    client = False
    server = False
    client_target = DEFAULT_PLATFORM
    server_target = DEFAULT_PLATFORM
    maps = None

    # Output directories
    out_dir = os.path.join(os.getcwd(), "Packaged")
    zip_dir = os.path.join(os.getcwd(), "Zips")

    for opt, arg in opts:
        match opt:
            case "--pre_reqs":
                pre_reqs = True
            case "--client":
                client = True
            case "--server":
                server = True
            case "--client_target":
                client_target = arg
            case "--server_target":
                server_target = arg
            case "--configuration":
                if arg not in CONFIGURATIONS:
                    logError(f"configuration must be one of the following values: {CONFIGURATIONS}")
                    sys.exit(2)
                configuration = arg
            case "--maps":
                maps = arg

    if not pre_reqs and not client and not server:
        logError("No actions to take based on passed arguments. Exiting...")
        sys.exit(2)
    
    checkRequiredArgs(configuration=configuration)

    logArgs(
        pre_reqs = pre_reqs,
        client = client,
        server = server,
        maps = maps,
        client_target = client_target,
        server_target = server_target,
        configuration = configuration,
        out_dir = out_dir,
        zip_dir = zip_dir
    )

    if pre_reqs:
        logStep(f"Building pre-reqs")
        logStep(f"Building Unreal Engine")
        buildEngineEditor()
        logStep(f"Building Engine components")
        buildUe4Components(configuration)
        logStep("Building project Development Editor")
        buildUe4(["Development", "Editor"])

    if client or server:

        if maps is None:
            logError("maps to build were not provided. Exiting...")
            sys.exit(2)

        logStep(f"Building Client/Server")

        logStep("Create output and zip directories")
        runPowershellCommand(f'mkdir "{zip_dir}"')
        runPowershellCommand(f'mkdir "{out_dir}"')

        if client:
            logStep(f"Build UE5 Client Target with configuration: {configuration}")
            buildUe4([configuration, "Client"])

        if server:
            logStep(f"Build UE5 Server Target with configuration: {configuration}")
            buildUe4([configuration, "Server"])

        logStep("Building, Cooking and Packaging Project")
        buildProject(
            client,
            client_target,
            server,
            server_target,
            configuration,
            maps,
            out_dir,
        )

        logStep("Compressing results")
        compressResults(out_dir)

def buildEngineEditor():
    callUe4Cli(["build-target", "UnrealEditor"])

def buildUe4Components(config):
    buildEngineBuildTarget("ShaderCompileWorker", config)


def buildEngineBuildTarget(component, config):
    build_target = ["build-target", component, config]
    callUe4Cli(build_target)

def compressResults(out_dir):
    sub_dirs = getSubdirectories(out_dir)
    for dir in sub_dirs:
        zipPath(dir, os.path.join(os.getcwd(), "Zips"))

def getSubdirectories(root):
    sub_dirs = []
    for it in os.scandir(root):
        if it.is_dir():
            sub_dirs.append(it.path)
    return sub_dirs

def zipPath(source_dir, output_dir):
    zip_path = os.path.join(output_dir, os.path.basename(source_dir) + ".zip")
    logInfo(f"Zipping {source_dir} to {zip_path}")
    run7zCommand(["a", zip_path, source_dir, "-bt"])

def buildProject(client, client_target, server, server_target, configuration, map_str, out_dir):
    if client is False and server is False:
        logWarning("Nothing to build, returning early...")
        return

    fullArgs = DEFAULT_PARAMS
    fullArgs += [r"-project=" + getUprojectPath()]
    fullArgs += [r"-map=" + map_str]
    fullArgs += [r"-configuration=" + configuration]

    if client:
        fullArgs += getClientParams(client_target)
    else:
        fullArgs += ["-noclient"]

    if server:
        fullArgs += getServerParams(server_target)

    fullArgs += [r"-archivedirectory=" + out_dir]

    runUatUe4(fullArgs)

def getClientParams(target):
    return ["-client", "-clienttargetplatform=" + target]

def getServerParams(target):
    return ["-server", "-servertargetplatform=" + target]


def getUprojectPath():
    uproject = PROJECT_NAME + ".uproject"
    return os.path.join(os.getcwd(), uproject)

def validateTools():
    callUe4Cli(["version"])
        
def buildUe4(args=None):
    build_args = addArgs(["build"], args)
    callUe4Cli(build_args)

def runUatUe4(args):
    uat_args = addArgs(["uat"], args)
    callUe4Cli(uat_args)

def runPowershellCommand(cmd):
    return cmdCall(["powershell", "-Command", cmd])

def run7zCommand(args):
    zip_args = addArgs(["7z"], args)
    return cmdCall(zip_args)

def callUe4Cli(args):
    ue4_args = addArgs(["ue4"], args)
    cmdCall(ue4_args)

def cmdCall(args):
    try:
        arg_str = subprocess.list2cmdline(args)
        logInfo(f"cmd call: {arg_str}")
        exit_code = subprocess.call(args)

        if exit_code > 0:
            logError(f"cmd call failed: {arg_str}")
            sys.exit(2)
    except:
        raise Exception("cmd call failed")


def addArgs(default, args):
    if (args is None) or (len(args) < 1):
        return default
    return default + args

def logStep(name):
    log(SEPARATOR)
    logInfo("Build Step: " + name)
    log(SEPARATOR)
    log(NEW_LINE)

def checkRequiredArgs(**kwargs):
    logInfo(f"Checking required arguments: {kwargs.items()}")
    for key, value in kwargs.items():
        if(value is None):
            logError(f'{key} is a required argument and was not provided. Exiting...')
            sys.exit(2)

def logArgs(**kwargs):
    logInfo("Command line arguments: ")
    for key, value in kwargs.items():
        logInfo(f'--{key} = {value}')

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
