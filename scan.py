#!/usr/bin/env python3
"""
Multi-language static analysis scanner
"""
import argparse
import os
import subprocess
import sys
import tempfile

"""
Supported language scan types
"""
scan_types = [
    "ansible",
    "aws",
    "bash",
    "credscan",
    "golang",
    "java",
    "kotlin",
    "nodejs",
    "puppet",
    "python",
    "ruby",
    "rust",
    "terraform",
    "yaml",
]

ignore_directories = [
    ".git",
    ".svn",
    ".mvn",
    ".idea",
    "dist",
    "bin",
    "obj",
    "backup",
    "docs",
    "tests",
    "test",
    "tmp",
]


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(
        description="Wrapper for various static analysis tools"
    )
    parser.add_argument(
        "--src", dest="src_dir", help="Source directory", required=True
    )
    parser.add_argument(
        "--out_dir", dest="reports_dir", help="Reports directory"
    )
    parser.add_argument(
        "--type",
        dest="scan_type",
        choices=scan_types,
        help="Override project type if auto-detection is incorrect",
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        dest="convert",
        help="Convert results to a normalized json lines format",
    )
    return parser.parse_args()


def scan(type, src, reports_dir, convert):
    """
    Method to initiate scan of the codebase

    Args:
      type Project type
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    if type:
        getattr(sys.modules[__name__], "%s_scan" % type)(
            src, reports_dir, convert
        )


def exec_tool(args):
    """
    Convenience method to invoke cli tools

    Args:
      args cli command and args
    """
    try:
        subprocess.run(args, stderr=subprocess.STDOUT, check=False, shell=False)
    except Exception as e:
        print(e)


def get_report_file(tool_name, reports_dir, convert, ext_name="json"):
    """
    Method to construct a report filename

    Args:
      tool_name Name of the tool
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
      ext_name Extension for the report
    """
    report_fname = ""
    if reports_dir:
        report_fname = os.path.join(
            reports_dir, tool_name + "-report." + ext_name
        )
    else:
        fp = tempfile.NamedTemporaryFile(delete=False)
        report_fname = fp.name
    return report_fname


def python_scan(src, reports_dir, convert):
    """
    Method to initiate scan of the python codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    bomgen(src, reports_dir, convert)
    bandit_scan(src, reports_dir, convert)
    ossaudit_scan(src, reports_dir, convert)


def bandit_scan(src, reports_dir, convert):
    """
    Method to initiate bandit scan of the python codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    convert_args = []
    report_fname = get_report_file("bandit", reports_dir, convert)
    if reports_dir or convert:
        convert_args = ["-o", report_fname, "-f", "json"]
    bandit_cmd = "bandit"
    bandit_args = [
        bandit_cmd,
        "-r",
        "-a",
        "vuln",
        "-ii",
        "-ll",
        *convert_args,
        "-x",
        ",".join(ignore_directories),
        src,
    ]
    exec_tool(bandit_args)


def find_python_reqfiles(path):
    """
    Method to find python requirements files

    Args:
      path Project dir
    """
    result = []
    req_files = ["requirements.txt", "Pipfile", "Pipfile.lock", "conda.yml"]
    for root, dirs, files in os.walk(path):
        for name in req_files:
            if name in files:
                result.append(os.path.join(root, name))
    return result


def find_jar_files():
    """
    Method to find jar files in the usual maven and gradle directories
    """
    result = []
    jar_lib_path = [
        os.path.join(os.environ["HOME"], ".m2"),
        os.path.join(os.environ["HOME"], ".gradle", "caches"),
    ]
    for path in jar_lib_path:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".jar"):
                    result.append(os.path.join(root, file))
    return result


def ossaudit_scan(src, reports_dir, convert):
    """
    Method to initiate ossaudit scan of the python codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    reqfiles = find_python_reqfiles(src)
    if not reqfiles:
        return
    aargs = []
    for req in reqfiles:
        aargs.append("-f")
        aargs.append(req)
    oss_cmd = "ossaudit"
    oss_args = [oss_cmd, *aargs]
    for c in "cve,name,version,cvss_score,title,description".split(","):
        oss_args.append("--column")
        oss_args.append(c)
    exec_tool(oss_args)


def java_scan(src, reports_dir, convert):
    """
    Method to initiate scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    bomgen(src, reports_dir, convert)
    pmd_scan(src, reports_dir, convert)
    findsecbugs_scan(src, reports_dir, convert)
    dep_check_scan(src, reports_dir, convert)


def pmd_scan(src, reports_dir, convert):
    """
    Method to initiate pmd scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    convert_args = []
    report_fname = get_report_file("pmd", reports_dir, convert, ext_name="csv")
    if reports_dir or convert:
        convert_args = ["-r", report_fname, "-f", "csv"]
    pmd_cmd = os.environ["PMD_CMD"].split(" ")
    pmd_args = [
        *pmd_cmd,
        "-no-cache",
        "--failOnViolation",
        "false",
        "-d",
        src,
        *convert_args,
        "-R",
        os.environ["APP_SRC_DIR"] + "/rules-pmd.xml",
    ]
    exec_tool(pmd_args)


def findsecbugs_scan(src, reports_dir, convert):
    """
    Method to initiate findsecbugs scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    report_fname = get_report_file(
        "findsecbugs", reports_dir, convert, ext_name="xml"
    )
    findsec_cmd = [
        "java",
        "-jar",
        os.environ["SPOTBUGS_HOME"] + "/lib/spotbugs.jar",
    ]
    jar_files = find_jar_files()
    with tempfile.NamedTemporaryFile(mode="w") as fp:
        fp.writelines([str(x) + "\n" for x in jar_files])
        jars_list = fp.name
        findsec_args = [
            *findsec_cmd,
            "-textui",
            "-include",
            os.environ["APP_SRC_DIR"] + "/spotbugs/include.xml",
            "-exclude",
            os.environ["APP_SRC_DIR"] + "/spotbugs/exclude.xml",
            "-noClassOk",
            "-auxclasspathFromFile",
            jars_list,
            "-sourcepath",
            src,
            "-quiet",
            "-medium",
            "-xml:withMessages",
            "-effort:max",
            "-nested:false",
            "-output",
            report_fname,
            src,
        ]
        exec_tool(findsec_args)


def dep_check_scan(src, reports_dir, convert):
    """
    Method to initiate dependency check scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    convert_args = []
    report_fname = get_report_file("dep_check", reports_dir, convert)
    if reports_dir or convert:
        convert_args = ["-o", report_fname, "-f", "JSON"]
    dc_cmd = "/opt/dependency-check/bin/dependency-check.sh"
    dc_args = [
        dc_cmd,
        "-s",
        src,
        *convert_args,
        "--enableExperimental",
        "--exclude",
        ",".join(ignore_directories),
    ]
    exec_tool(dc_args)


def nodejs_scan(src, reports_dir, convert):
    """
    Method to initiate scan of the node.js codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    bomgen(src, reports_dir, convert)
    retirejs_scan(src, reports_dir, convert)


def retirejs_scan(src, reports_dir, convert):
    """
    Method to initiate retire.js scan of the node.js codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    convert_args = []
    report_fname = get_report_file("retire", reports_dir, convert)
    if reports_dir or convert:
        convert_args = [
            "--outputpath",
            report_fname,
            "--outputformat",
            "jsonsimple",
        ]
    retire_cmd = "retire"
    retire_args = [
        retire_cmd,
        "--path",
        src,
        "-p",
        *convert_args,
        "--ignore",
        ",".join(ignore_directories),
    ]
    exec_tool(retire_args)


def bomgen(src, reports_dir, convert):
    """
    Method to generate cyclonedx bom file using cdxgen

    Args:
      src Project dir
      reports_dir Directory for output reports
      convert Boolean to enable normalisation of reports json
    """
    report_fname = get_report_file("bom", reports_dir, convert, ext_name="xml")
    bom_args = ["cdxgen", "-o", report_fname, src]
    exec_tool(bom_args)


if __name__ == "__main__":
    args = build_args()
    type = args.scan_type
    scan(type, args.src_dir, args.reports_dir, args.convert)