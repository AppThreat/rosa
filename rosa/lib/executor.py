import io
import os
import subprocess

from rich.progress import Progress

import rosa.lib.config as config
import rosa.lib.convert as convertLib
import rosa.lib.utils as utils
from rosa.lib.logger import DEBUG, LOG, console
from rosa.lib.telemetry import track


def use_java(env):
    """
    Method to use the right java environment based on the environment variables SCAN_JAVA_HOME, SCAN_JAVA_11_HOME
    :param env: Copy of all environment variables
    :return: Env list with PATH suffixed by correct java home
    """
    if env.get("SCAN_JAVA_HOME"):
        env["PATH"] = env["PATH"] + ":" + os.path.join(env.get("SCAN_JAVA_HOME"), "bin")
        env["JAVA_HOME"] = env.get("SCAN_JAVA_HOME")
    elif env.get("SCAN_JAVA_11_HOME"):
        env["JAVA_HOME"] = env.get("SCAN_JAVA_11_HOME")
        env["PATH"] = (
            env["PATH"] + ":" + os.path.join(env.get("SCAN_JAVA_11_HOME"), "bin")
        )
    return env


def should_suppress_output(type_str, command):
    """
    Method to find if the tool's output should be suppressed
    """
    if "credscan" in type_str:
        return True
    if "php" in type_str and not LOG.isEnabledFor(DEBUG):
        return True
    if command in ["gitleaks"]:
        return True
    if command in ["psalm"] and not LOG.isEnabledFor(DEBUG):
        return True
    return False


def should_convert(tool_name, command, report_fname):
    """
    Method to find if sarif conversion should be performed
    """
    if (
        "init" not in tool_name
        and (
            config.tool_purpose_message.get(command)
            or "audit" in tool_name
            or "source" in tool_name
        )
        and os.path.isfile(report_fname)
    ):
        return True
    return False


def exec_tool(  # scan:ignore
    tool_name, args, cwd=None, env=utils.get_env(), stdout=subprocess.DEVNULL
):
    """
    Convenience method to invoke cli tools

    Args:
      tool_name Tool name
      args cli command and args
      cwd Current working directory
      env Environment variables
      stdout stdout configuration for run command

    Returns:
      CompletedProcess instance
    """
    with Progress(
        console=console,
        transient=True,
        redirect_stderr=False,
        redirect_stdout=False,
        refresh_per_second=1,
    ) as progress:
        task = None
        try:
            env = use_java(env)
            LOG.debug('⚡︎ Executing {} "{}"'.format(tool_name, " ".join(args)))
            stderr = subprocess.DEVNULL
            if LOG.isEnabledFor(DEBUG):
                stderr = subprocess.STDOUT
            tool_verb = "Scanning with"
            if "init" in tool_name:
                tool_verb = "Initializing"
            elif "build" in tool_name:
                tool_verb = "Building with"
            task = progress.add_task(
                "[green]" + tool_verb + " " + tool_name, total=100, start=False
            )
            cp = subprocess.run(
                args,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                env=env,
                check=False,
                shell=False,
                encoding="utf-8",
            )
            if cp and stdout == subprocess.PIPE:
                for line in cp.stdout:
                    progress.update(task, completed=5)
            if (
                cp
                and LOG.isEnabledFor(DEBUG)
                and cp.returncode
                and cp.stdout is not None
            ):
                LOG.debug(cp.stdout)
            progress.update(task, completed=100, total=100)
            return cp
        except Exception as e:
            if task:
                progress.update(task, completed=20, total=10, visible=False)
            if not LOG.isEnabledFor(DEBUG):
                LOG.info(
                    f"{tool_name} has reported few errors. To view, pass the environment variable SCAN_DEBUG_MODE=debug"
                )
            LOG.debug(e)
            return None


def execute_default_cmd(  # scan:ignore
    cmd_map_list,
    type_str,
    tool_name,
    src,
    reports_dir,
    scan_mode,
    repo_context,
):
    """
    Method to execute default command for the given type

    Args:
      cmd_map_list Default commands in the form of a dict (multiple) or list
      type_str Project type
      tool_name Tool name
      src Project dir
      reports_dir Directory for output reports
      scan_mode Scan mode string
      repo_context Repo context
    """
    # Check if there is a default command specified for the given type
    # Create the reports dir
    report_fname_prefix = os.path.join(reports_dir, tool_name + "-report")
    # Look for any additional direct arguments for the tool and inject them
    if config.get(tool_name + "_direct_args"):
        direct_args = config.get(tool_name + "_direct_args").split(" ")
        if direct_args:
            cmd_map_list += direct_args
    src_or_file = src
    default_cmd = " ".join(cmd_map_list) % dict(
        src=src,
        src_or_file=src_or_file,
        reports_dir=reports_dir,
        report_fname_prefix=report_fname_prefix,
        type=type_str,
        scan_mode=scan_mode,
    )
    # Try to detect if the output could be json
    outext = ".out"
    if "json" in default_cmd:
        outext = ".json"
    elif "csv" in default_cmd:
        outext = ".csv"
    elif "sarif" in default_cmd:
        outext = ".sarif"
    elif "xml" in default_cmd:
        outext = ".xml"
    report_fname = report_fname_prefix + outext

    # If the command doesn't support file output then redirect stdout automatically
    stdout = None
    if LOG.isEnabledFor(DEBUG):
        stdout = None
    if reports_dir and report_fname_prefix not in default_cmd:
        report_fname = report_fname_prefix + outext
        stdout = io.open(report_fname, "w", encoding="utf-8")
        LOG.debug("Output will be written to {}".format(report_fname))

    # If the command is requesting list of files then construct the argument
    filelist_prefix = "(filelist="
    if default_cmd.find(filelist_prefix) > -1:
        si = default_cmd.find(filelist_prefix)
        ei = default_cmd.find(")", si + 10)
        ext = default_cmd[si + 10 : ei]
        filelist = utils.find_files(src, ext)
        # Temporary fix for the yaml issue
        if ext == "yaml":
            yml_list = utils.find_files(src, "yml")
            if yml_list:
                filelist.extend(yml_list)
        delim = " "
        default_cmd = default_cmd.replace(
            filelist_prefix + ext + ")", delim.join(filelist)
        )
    cmd_with_args = default_cmd.split(" ")
    # Suppress psalm output
    if should_suppress_output(type_str, cmd_with_args[0]):
        stdout = subprocess.DEVNULL
    exec_tool(
        tool_name,
        cmd_with_args,
        cwd=os.getcwd() if "image" in tool_name else src,
        stdout=stdout,
    )
    # Should we attempt to convert the report to sarif format
    if should_convert(tool_name, cmd_with_args[0], report_fname):
        crep_fname = utils.get_report_file(tool_name, reports_dir, ext_name="sarif")
        if (
            cmd_with_args[0] == "java"
            or "pmd-bin" in cmd_with_args[0]
            or "php" in tool_name
        ):
            convertLib.convert_file(
                tool_name,
                cmd_with_args,
                src,
                report_fname,
                crep_fname,
            )
        else:
            convertLib.convert_file(
                cmd_with_args[0],
                cmd_with_args[1:],
                src,
                report_fname,
                crep_fname,
            )
        try:
            if not LOG.isEnabledFor(DEBUG):
                os.remove(report_fname)
        except Exception:
            LOG.debug("Unable to remove file {}".format(report_fname))
