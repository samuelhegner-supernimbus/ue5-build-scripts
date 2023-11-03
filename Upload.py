import os
import subprocess
import sys, getopt


def main(argv):
    try:
        callAwsCli(["--version"])
    except:
        logError("Issue calling AWS cli")
        sys.exit(2)

    try:
        opts, args = getopt.getopt(
            argv, "", ["local_folder=", "remote_folder=", "bucket=", "generate_links", "link_expiry="]
        )
    except getopt.GetoptError:
        logError("Incorrect arguments passed to script")
        sys.exit(2)

    # Required args
    local_folder = None
    remote_folder = None
    bucket = None

    # Optional args
    generate_link = False
    expiry = 172800 # 2 days in seconds

    for opt, arg in opts:
        match opt:
            case "--bucket":
                bucket = cleanString(arg)
            case "--local_folder":
                local_folder = cleanString(arg)
            case "--remote_folder":
                remote_folder = cleanString(arg)
            case "--generate_links":
                generate_link = True
            case "--link_expiry":
                expiry = arg

    checkRequiredArgs(local_folder=local_folder, remote_folder=remote_folder, bucket=bucket)

    syncFolder(local_folder, remote_folder, bucket)

    if generate_link is True:
        file_names = listFilesAtDir(bucket, remote_folder)
        urls = generate_presigned_urls(bucket, remote_folder, file_names, expiry)
        save_dict_to_file(urls)



def listFilesAtDir(bucket, dir):

    logInfo(f"Listing files in dir: {dir}")

    args = [    
        "aws",
        "s3",
        "ls",
        f"s3://{bucket}/{dir}/"
    ]

    output = subprocess.check_output(args)
    lines = output.decode().splitlines()
    file_names = [line.split()[-1] for line in lines if not line.endswith("/")]

    logInfo(f"Found files: {file_names}")

    return file_names

def generate_presigned_urls(bucket, dir, keys, expiration):
    
    logInfo(f"Generating urls for files: {keys}")

    urls = {}
    for key in keys:
        args = [
            "aws",
            "s3",
            "presign",
            f"s3://{bucket}/{dir}/{key}",
            "--expires-in",
            str(expiration),
        ]
        output = subprocess.check_output(args)
        clean_output  = output.decode().strip()
        urls[key] = clean_output
        logInfo("Created url: " + clean_output)

    logInfo('Returning all urls...')
    return urls

def syncFolder(local_dir, remote_dir, bucket, storage_class="STANDARD"):
    logInfo("Uploading files to S3...")

    for dirpath, dir_names, file_names in os.walk(local_dir):
        for file_name in file_names:
            local_path = os.path.join(dirpath, file_name)
            remote_file_name = file_name.replace(" ", "-")
            remote_path = f"s3://{bucket}/{remote_dir}/{remote_file_name}"
            callS3(
                [
                    "cp",
                    local_path,
                    remote_path,
                    "--storage-class=" + storage_class,
                    "--no-progress",
                ]
            )
    

def save_dict_to_file(dictionary, filename="urls.txt"):
    logInfo(f"Writing Dict to file: {dictionary}")

    try:
        with open(filename, "w") as file:
            for key, value in dictionary.items():
                file.write(f"{str(key)}: {str(value)}\n")
    except IOError as e:
        logError(f"An I/O error occurred: {e.strerror}")
    
    logInfo("finished writing dictionary to file")


def callS3(args):
    callAwsCli(["s3"] + args)


def callAwsCli(args):
    aws_call = ["aws"] + args
    logInfo(f"AWS cli call: {subprocess.list2cmdline(aws_call)}")
    try:
        subprocess.run(aws_call)
    except:
        raise Exception("Aws command failed")

def cleanString(s):
    return s.replace(" ", "").replace("\n", "")

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
