import sys
import os
import yaml
import logging
import importlib
import importlib.util
import subprocess
import shutil

# Configure logging format
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tlnw-tools")

def find_tools_config():
    # 1. Check current working directory
    cwd_path = os.path.join(os.getcwd(), "tools.yml")
    if os.path.exists(cwd_path):
        return cwd_path
    
    # 2. Check sibling to this module's parent (dev mode)
    dev_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools.yml")
    if os.path.exists(dev_path):
        return dev_path
    
    # 3. Check inside the module directory itself (packaged mode)
    pkg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools.yml")
    if os.path.exists(pkg_path):
        return pkg_path
    
    return None

def load_tools_config():
    config_path = find_tools_config()
    if not config_path:
        logger.error("Configuration file 'tools.yml' not found in workspace or package.")
        sys.exit(1)
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse tools.yml: {e}")
        sys.exit(1)

def is_package_installed(module_name):
    if not module_name:
        return False
    top_level = module_name.split('.')[0]
    try:
        spec = importlib.util.find_spec(top_level)
        return spec is not None
    except Exception:
        return False

def install_package(package_name):
    logger.info(f"Package '{package_name}' not found. Installing dynamically from PyPI...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        logger.info(f"Successfully installed package '{package_name}'.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to dynamically install package '{package_name}': {e}")
        return False

def run_inprocess(tool_info, tool_args):
    module_name = tool_info.get("module")
    entry_point_name = tool_info.get("entry_point", "main")
    
    if not module_name:
        logger.error(f"Missing 'module' entry for tool '{tool_info.get('name')}' in tools.yml.")
        sys.exit(1)
        
    # Check installation
    if not is_package_installed(module_name):
        package_name = tool_info.get("package")
        if not package_name:
            logger.error(f"Tool '{tool_info.get('name')}' is not installed, and no 'package' is specified in tools.yml to install it.")
            sys.exit(1)
        if not install_package(package_name):
            sys.exit(1)
            
    # Dynamic import and execution
    try:
        # Clear module from sys.modules to ensure a fresh import after installation
        if module_name in sys.modules:
            del sys.modules[module_name]
            
        module = importlib.import_module(module_name)
        entry_point = getattr(module, entry_point_name)
    except Exception as e:
        logger.error(f"Failed to load entry point '{entry_point_name}' from module '{module_name}': {e}")
        sys.exit(1)
        
    # Replace sys.argv with our tool arguments
    # argv[0] is typically the script or subcommand name
    sys.argv = [tool_info.get("name")] + tool_args
    
    try:
        return entry_point()
    except SystemExit as se:
        return se.code
    except Exception as e:
        logger.error(f"Error during tool execution: {e}")
        return 1

def run_subprocess(tool_info, tool_args):
    tool_name = tool_info.get("name")
    package_name = tool_info.get("package")
    module_name = tool_info.get("module")
    
    # Check if executable / script is on path
    executable_path = shutil.which(tool_name)
    
    if not executable_path:
        # If not on path, verify if installed via python module, otherwise install
        if not is_package_installed(module_name):
            if not package_name:
                logger.error(f"Tool '{tool_name}' executable not found on PATH, and no 'package' specified to install.")
                sys.exit(1)
            if not install_package(package_name):
                sys.exit(1)
        
        # Try finding executable again after install
        executable_path = shutil.which(tool_name)
        if not executable_path:
            # Fall back to running via python -m
            if module_name:
                logger.debug(f"Executable '{tool_name}' not on PATH. Falling back to executing via 'python -m {module_name}'.")
                cmd = [sys.executable, "-m", module_name] + tool_args
                try:
                    res = subprocess.run(cmd)
                    return res.returncode
                except Exception as e:
                    logger.error(f"Failed to execute module '{module_name}' via subprocess: {e}")
                    sys.exit(1)
            else:
                logger.error(f"Executable '{tool_name}' not found on PATH, and no module fallback available.")
                sys.exit(1)
                
    # If executable is found
    logger.debug(f"Executing '{executable_path}' with args {tool_args} via subprocess.")
    try:
        res = subprocess.run([executable_path] + tool_args)
        return res.returncode
    except Exception as e:
        logger.error(f"Failed to run executable '{executable_path}': {e}")
        return 1

def print_help(config):
    print("Usage: tlnw-tools [--debug] <tool> [args...]")
    print("\nCommon Options:")
    print("  -h, --help    Show this help message and exit")
    print("  --debug       Enable debug-level logging")
    print("\nAvailable Tools:")
    
    tools = config.get("tools", [])
    if not tools:
        print("  (No tools registered)")
        return
        
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "No description available.")
        print(f"  {name:<15} {desc}")
    print()

def main():
    config = load_tools_config()
    
    # Parse CLI arguments manually to support generic tool arguments forwarding
    args = sys.argv[1:]
    
    # Handle help at main level
    if not args or "-h" in args or "--help" in args:
        # If we have args but first arg is a tool, let the tool handle its own help
        if args and args[0] in [t.get("name") for t in config.get("tools", [])]:
            # This is help for a specific tool, let the tool handle it
            pass
        else:
            print_help(config)
            sys.exit(0)
            
    # Parse debug flag
    debug_mode = False
    if "--debug" in args:
        debug_mode = True
        logger.setLevel(logging.DEBUG)
        logging.getLogger("").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled for tlnw-tools CLI.")
        # Remove --debug from args so it doesn't pollute subcommand matching
        args.remove("--debug")
        
    if not args:
        print_help(config)
        sys.exit(1)
        
    tool_name = args[0]
    tool_args = args[1:]
    
    # Re-append --debug if we had it, so the tool also gets it if it wants it
    if debug_mode and "--debug" not in tool_args:
        tool_args.append("--debug")
        
    # Find matching tool
    matching_tool = None
    for tool in config.get("tools", []):
        if tool.get("name") == tool_name:
            matching_tool = tool
            break
            
    if not matching_tool:
        print(f"Error: Tool '{tool_name}' not registered in tools.yml.")
        print_help(config)
        sys.exit(1)
        
    # Execute according to mode
    mode = matching_tool.get("execution_mode", "inprocess_import")
    logger.debug(f"Executing tool '{tool_name}' in '{mode}' mode.")
    
    if mode == "subprocess":
        exit_code = run_subprocess(matching_tool, tool_args)
    else:
        exit_code = run_inprocess(matching_tool, tool_args)
        
    sys.exit(exit_code or 0)

if __name__ == "__main__":
    main()
