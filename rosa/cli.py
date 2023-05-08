#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Risk Oriented Security Analysis
"""
import argparse
import os
import signal
import sys
import tempfile
import time
import uuid
from multiprocessing import Pool
from pathlib import Path

import rosa.lib.analysis as analysis
import rosa.lib.config as config
import rosa.lib.context as context
import rosa.lib.convert as convertLib
import rosa.lib.utils as utils
from rosa.lib.builder import auto_build
from rosa.lib.executor import exec_tool, execute_default_cmd
from rosa.lib.integration import provider
from rosa.lib.logger import LOG, console
from rosa.lib.pyt.cfg_analyzer import deep_analysis
from rosa.lib.pyt.formatters.json import report as py_json_report
from rosa.lib.telemetry import track

product_logo = """
██████╗  ██████╗ ███████╗ █████╗
██╔══██╗██╔═══██╗██╔════╝██╔══██╗
██████╔╝██║   ██║███████╗███████║
██╔══██╗██║   ██║╚════██║██╔══██║
██║  ██║╚██████╔╝███████║██║  ██║
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
"""


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="Risk oriented security analysis")
    parser.add_argument("-i", "--src", dest="src_dir", help="Source directory")
    parser.add_argument("-o", "--out_dir", dest="reports_dir", help="Reports directory")
    parser.add_argument(
        "-t",
        "--type",
        dest="scan_type",
        help="Override project type if auto-detection is incorrect. Comma separated values for multiple types. Eg: python,bash,credscan",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        default=False,
        dest="auto_build",
        help="Attempt to automatically build the project for supported types",
    )
    parser.add_argument(
        "--no-error",
        action="store_true",
        default=False,
        dest="noerror",
        help="Continue on error to prevent build from breaking",
    )
    parser.add_argument(
        "-m",
        "--mode",
        default="ci",
        dest="scan_mode",
        help="Scan mode to use ci, ide, pr, release, deploy",
    )
    return parser.parse_args()


def scan_project_types(pool, type_list, src, reports_dir, scan_mode, repo_context):
    """
    Method to initiate scan of the codebase

    Args:
      pool Process pool to submit tasks to
      type_list List of project type
      src Project dir
      reports_dir Directory for output reports
      scan_mode Scan mode string
      repo_context Repo context
    """
    for type_str in type_list:
        # Find if there is any scan mode specific config
        cmd_map_list = config.get("scan_tools_args_map").get(type_str + "-" + scan_mode)
        if not cmd_map_list:
            cmd_map_list = config.get("scan_tools_args_map").get(type_str)
        if cmd_map_list:
            # Default command list can be in the form of a list or dict
            if isinstance(cmd_map_list, list):
                pool.apply_async(
                    execute_default_cmd,
                    (
                        cmd_map_list,
                        type_str,
                        type_str,
                        src,
                        reports_dir,
                        scan_mode,
                        repo_context,
                    ),
                )
            elif isinstance(cmd_map_list, dict):
                for cmd_key, cmd_val in cmd_map_list.items():
                    if "init" in cmd_key or type_str == "php":
                        execute_default_cmd(
                            cmd_val,
                            type_str,
                            cmd_key,
                            src,
                            reports_dir,
                            scan_mode,
                            repo_context,
                        )
                    else:
                        pool.apply_async(
                            execute_default_cmd,
                            (
                                cmd_val,
                                type_str,
                                cmd_key,
                                src,
                                reports_dir,
                                scan_mode,
                                repo_context,
                            ),
                        )
        else:
            # Look for any _scan function in this module for execution
            try:
                dfn = getattr(sys.modules[__name__], "%s_scan" % type_str, None)
                if dfn:
                    pool.apply_async(dfn, (src, reports_dir, repo_context))
                else:
                    x_scan(type_str, src, reports_dir, repo_context)
            except Exception as e:
                LOG.debug(e)
                LOG.warning(
                    "Scan using the {} plugin did not produce valid result".format(
                        type_str
                    )
                )


def init_worker():
    """
    Handler for worker processes to let their parent handle interruptions
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def scan(type_list, src, reports_dir, scan_mode, repo_context):
    """
    Wrapper around scan_project_types to scan the codebase

    Args:
      type_list List of project type
      src Project dir
      reports_dir Directory for output reports
      scan_mode Scan mode string
      repo_context Repo context
    """
    if __name__ in ("__main__", "rosa.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                scan_project_types(
                    pool, type_list, src, reports_dir, scan_mode, repo_context
                )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def x_scan(type_str, src, reports_dir, repo_context):
    """
    Default placeholder scan method for missing scanners

    Args:
      type_str Project type
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    # Report file in the reports dir
    report_fname = utils.get_report_file(
        f"source-{type_str}", reports_dir, ext_name="json"
    )
    # Report file in the source dir
    src_report_fname = utils.get_report_file(f"source-{type_str}", src, ext_name="json")
    # SARIF file name for conversion
    crep_fname = utils.get_report_file(
        f"source-{type_str}", reports_dir, ext_name="sarif"
    )
    # If there is an existing report available simply use it
    if os.path.exists(crep_fname):
        LOG.info(f"Found an existing SARIF report at {crep_fname} :thumbsup:")
    elif os.path.exists(report_fname):
        convertLib.convert_file(
            f"source-{type_str}",
            [],
            src,
            report_fname,
            crep_fname,
        )
    elif os.path.exists(src_report_fname):
        convertLib.convert_file(
            f"source-{type_str}",
            [],
            src,
            src_report_fname,
            crep_fname,
        )
    else:
        LOG.info(
            f"Is there any open-source scanner for {type_str}? Please let us know :thumbsup:"
        )


def python_scan(src, reports_dir, repo_context):
    """
    Method to initiate scan of the python codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    py_deep_scan(src, reports_dir, repo_context)


def py_deep_scan(src, reports_dir, repo_context):
    """
    Method to perform deep scan of python codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    report_fname = utils.get_report_file("taint-python", reports_dir, ext_name="json")
    web_route_only = config.get("WEB_ROUTE_ONLY", False)
    py_files = utils.find_files(src, ".py")
    LOG.debug(f"Scanning {len(py_files)} python files ...")
    try:
        vulnerabilities, insights, has_unsanitised_vulnerabilities = deep_analysis(
            src, py_files
        )
        if not vulnerabilities and not insights:
            LOG.debug(f"taint-python has not found any vulnerabilities or insights")
            return
        py_json_report(vulnerabilities, insights, report_fname)
        crep_fname = utils.get_report_file(
            "taint-python", reports_dir, ext_name="sarif"
        )
        convertLib.convert_file(
            "taint-python",
            ["-j", "-a", "e", "-o", report_fname],
            src,
            report_fname,
            crep_fname,
        )
    except Exception as e:
        LOG.debug(e)


def java_scan(src, reports_dir, repo_context):
    """
    Method to initiate scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    findsecbugs_scan(src, reports_dir, repo_context)
    pmd_scan(src, reports_dir, repo_context)


def csharp_scan(src, reports_dir, repo_context):
    """
    Method to initiate scan of the csharp codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    LOG.info("c# is not supported yet!")


def pmd_scan(src, reports_dir, repo_context):
    """
    Method to initiate pmd scan of the java codebase
    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    convert_args = []
    report_fname = utils.get_report_file("source-java", reports_dir, ext_name="csv")
    convert_args = ["-r", report_fname, "-f", "csv"]
    pmd_cmd = config.get("PMD_CMD").split(" ")
    if not utils.check_command(pmd_cmd[0]):
        LOG.warning("Java scanner is not available.")
        return
    pmd_args = [
        *pmd_cmd,
        "--no-cache",
        "--fail-on-violation",
        "false",
        "-language",
        "java",
        "-d",
        src,
        *convert_args,
        "-R",
        config.get("TOOLS_CONFIG_DIR") + "/rules-pmd.xml",
    ]
    exec_tool("source-java", pmd_args, src)
    crep_fname = utils.get_report_file("source-java", reports_dir, ext_name="sarif")
    convertLib.convert_file(
        "source-java",
        pmd_args[1:],
        src,
        report_fname,
        crep_fname,
    )


def findsecbugs_scan(src, reports_dir, repo_context):
    """
    Method to initiate findsecbugs scan of the java codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    if not config.get("SPOTBUGS_HOME"):
        LOG.warning("Java class analyzer is not available.")
        return
    report_fname = utils.get_report_file("class", reports_dir, ext_name="xml")
    findsec_cmd = [
        "java",
        "-jar",
        config.get("SPOTBUGS_HOME") + "/lib/spotbugs.jar",
    ]
    jar_files = utils.find_jar_files()
    src_or_file = src
    with tempfile.NamedTemporaryFile(mode="w") as fp:
        fp.writelines([str(x) + "\n" for x in jar_files])
        jars_list = fp.name
        findsec_args = [
            *findsec_cmd,
            "-textui",
            "-include",
            config.get("TOOLS_CONFIG_DIR") + "/spotbugs/include.xml",
            "-exclude",
            config.get("TOOLS_CONFIG_DIR") + "/spotbugs/exclude.xml",
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
            src_or_file,
        ]
        exec_tool("class", findsec_args, src)
        # We need the filelist to fix the file location paths
        j_files = utils.find_files(src, ".java")
        crep_fname = utils.get_report_file("class", reports_dir, ext_name="sarif")
        convertLib.convert_file(
            "class",
            findsec_args[1:],
            src,
            report_fname,
            crep_fname,
            j_files,
        )


def nodejs_scan(src, reports_dir, repo_context):
    """
    Method to initiate scan of the node.js codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    LOG.info("Scanning JavaScript projects is currently not possible with rosa.")


def ts_scan(src, reports_dir, repo_context):
    """
    Method to initiate scan of the TypeScript codebase

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    LOG.info("Scanning TypeScript projects is currently not possible with rosa.")


def bomgen(src, reports_dir, repo_context):
    """
    Method to generate cyclonedx bom file using cdxgen

    Args:
      src Project dir
      reports_dir Directory for output reports
      repo_context Repo context
    """
    report_fname = utils.get_report_file("bom", reports_dir, ext_name="xml")
    bom_args = ["cdxgen", "-o", report_fname, src]
    exec_tool("cdxgen", bom_args, src)


def create_empty_result(src_dir, reports_dir):
    # Create empty sarif file to prevent codeql upload action from failing
    crep_fname = utils.get_report_file("empty-scan", reports_dir, ext_name="sarif")
    convertLib.report("empty-scan", [], src_dir, None, [], [], crep_fname, None)


def should_skip(src_dir, reports_dir, repo_context, scan_mode):
    """
    Method to check if a scan should be skipped

    :param src_dir: Source directory
    :param reports_dir: Reports directory
    :param repo_context: Repo context
    :param scan_mode: Scan mode
    :return: True if scan should be skipped. False otherwise.
    """
    if (
        scan_mode == "ci"
        and repo_context.get("botUser")
        and config.get("skip_bot_triggers")
    ):
        LOG.info(
            f"""Scan will be skipped since the build was triggered by a bot '{repo_context.get("invokedBy")}'"""
        )
        create_empty_result(src_dir, reports_dir)
        return True
    return False


def should_annotate(git_provider, repo_context, findings_file, depscan_files):
    """
    Method to check if the build or PR should get annotated.

    :param git_provider: Git Provider string
    :param repo_context: Repo context
    :param findings_file: Findings json file
    :return: True if build should be annotated. False otherwise.
    """
    annotate_flag = config.get("scan_annotate_pr", "")
    if (
        annotate_flag == "true" or annotate_flag == "1" or git_provider == "bitbucket"
    ) and (findings_file or depscan_files):
        return True
    if repo_context.get("pullRequest") and git_provider == "gitlab":
        LOG.info(
            "Scan can automatically add the summary as a merge request comment. To learn more - https://slscan.io/en/latest/integrations/gitlab/#merge-request-comment-feature"
        )
    return False


def main():
    start_time = time.monotonic_ns()
    args = build_args()
    src_dir = args.src_dir
    type = args.scan_type
    reports_base_dir = os.getcwd()
    if not args.src_dir:
        src_dir = os.getcwd()
    scan_mode = args.scan_mode
    if scan_mode:
        scan_mode = scan_mode.lower()
    # Set the source directory as an environment variable if not set
    if os.getenv("SAST_SCAN_SRC_DIR") is None:
        config.set("SAST_SCAN_SRC_DIR", src_dir)
    # Get or construct the run uuid
    run_uuid = os.environ.get("SCAN_ID", str(uuid.uuid4()))
    config.set("run_uuid", run_uuid)
    repo_context = context.find_repo_details(src_dir)
    workspace = os.getenv("WORKSPACE")
    if workspace is None and scan_mode != "ide":
        # In case of GitHub action empty workspace forces relative url
        if os.environ.get("GITHUB_ACTION") or os.environ.get("GITHUB_RUN_ID"):
            workspace = ""
        else:
            workspace = utils.get_workspace(repo_context)
        if workspace:
            config.set("WORKSPACE", workspace)
    config.reload()
    # Identify project type
    if not type:
        # Check the local config first. If not try auto detection
        type = config.get("scan_type")
        if type:
            type = type.split(",")
        else:
            type = utils.detect_project_type(src_dir, scan_mode)
    else:
        type = type.split(",")
    reports_dir = args.reports_dir
    if not reports_dir:
        if "docker" in type or "podman" in type or "container" in type:
            reports_dir = os.path.join(reports_base_dir, "reports")
        else:
            reports_dir = os.path.join(src_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    # Should we skip this scan
    if should_skip(src_dir, reports_dir, repo_context, scan_mode):
        sys.exit(0)
    console.print(product_logo, style="info")
    LOG.info("Scanning {} using plugins {}".format(src_dir, type))
    if args.auto_build or config.get("scan_auto_build"):
        build_res = auto_build(type, src_dir, reports_dir)
        if not build_res:
            LOG.debug(
                "Automatic build was not successful. Please run scan after the build step"
            )
    scan(type, src_dir, reports_dir, scan_mode, repo_context)
    sarif_files = [p.as_posix() for p in Path(reports_dir).rglob("*.sarif")]
    depscan_files = [p.as_posix() for p in Path(reports_dir).rglob("depscan*.json")]
    agg_fname = None
    baseline_fname = os.path.join(reports_dir, ".sastscan.baseline")
    if scan_mode != "ide":
        agg_fname = utils.get_report_file("scan-full", reports_dir, ext_name="json")
    report_summary, build_status = analysis.summary(
        sarif_files=sarif_files,
        depscan_files=depscan_files,
        aggregate_file=agg_fname,
        baseline_file=baseline_fname,
    )
    if report_summary:
        analysis.print_table(report_summary)
        end_time = time.monotonic_ns()
        track(
            {
                "id": run_uuid,
                "repo_context": repo_context,
                "report_summary": report_summary,
                "scan_mode": scan_mode,
                "repo_type": type,
                "scan_time_sec": round((end_time - start_time) / 1000000000, 2),
            }
        )
        if not sarif_files:
            create_empty_result(src_dir, reports_dir)
        if not args.noerror and not scan_mode == "ide":
            sys.exit(1 if build_status == "fail" else 0)
    else:
        LOG.debug(
            "No scan summary was produced - {}, {}".format(sarif_files, agg_fname)
        )
        create_empty_result(src_dir, reports_dir)


if __name__ == "__main__":
    main()
