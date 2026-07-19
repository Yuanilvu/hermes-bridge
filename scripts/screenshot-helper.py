#!/usr/bin/env python3
"""
Wayland screenshot helper — uses D-Bus portal via gdbus
Bypasses Python dbus module issues by calling gdbus CLI.
"""
import subprocess
import sys
import os
import json
import tempfile
import time
import base64

def take_screenshot(output_path: str, timeout: int = 10) -> bool:
    """Take a screenshot using the D-Bus portal's Screenshot API.
    
    Uses the synchronous approach:
    1. Call the portal Screenshot method (it returns async)
    2. Use gdbus monitor to catch the response signal
    """
    # We need to:
    # 1. Generate a unique request path
    # 2. Call the Screenshot portal method
    # 3. Listen for the Request.Response signal
    # 4. Extract the URI from the response
    
    # The token is used to match request to response
    import uuid
    token = str(uuid.uuid4())[:8]
    
    # Set up env for D-Bus
    env = os.environ.copy()
    
    # Start the gdbus monitor in background to capture response
    monitor_cmd = [
        "gdbus", "monitor", "--session",
        "--dest", "org.freedesktop.portal.Desktop",
    ]
    
    try:
        # Start the monitor
        monitor = subprocess.Popen(
            monitor_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
        )
        
        # Call the portal Screenshot method
        # The method takes (parent_window: s, options: a{sv})
        # We pass interactive=false to avoid user prompt
        call_cmd = [
            "gdbus", "call", "--session",
            "--dest", "org.freedesktop.portal.Desktop",
            "--object-path", "/org/freedesktop/portal/desktop",
            "--method", "org.freedesktop.portal.Screenshot.Screenshot",
            "",  # no parent window
            f"dict:entry:string,boolean:'interactive',false",
        ]
        
        call_result = subprocess.run(
            call_cmd,
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        
        # Read the response from monitor
        # The response signal looks like:
        # /org/freedesktop/portal/desktop/request/...: org.freedesktop.portal.Request.Response ...
        
        # Wait a short time for the response
        import select
        start_time = time.time()
        response_data = []
        
        while time.time() - start_time < timeout:
            reads, _, _ = select.select([monitor.stdout], [], [], 0.5)
            if reads:
                line = monitor.stdout.readline()
                if "Request.Response" in line:
                    response_data.append(line)
                    break
                elif line:
                    response_data.append(line)
            else:
                # Check if we got the call response already
                break
        
        monitor.terminate()
        monitor.wait(timeout=3)
        
        # Parse the response to find the URI
        for line in response_data:
            if "uri:" in line or "file://" in line:
                # Extract the file URI
                import re
                uri_match = re.search(r"'(file://[^']+)'", line)
                if uri_match:
                    uri = uri_match.group(1)
                    # uri is like file:///tmp/...png
                    filepath = uri.replace("file://", "")
                    import urllib.parse
                    filepath = urllib.parse.unquote(filepath)
                    if os.path.exists(filepath):
                        os.rename(filepath, output_path)
                        return True
        
        # Fallback: the screenshot might have been saved
        # Check common locations
        for f in os.listdir("/tmp"):
            if f.endswith(".png") and f.startswith("screenshot-"):
                fp = os.path.join("/tmp", f)
                if os.path.getsize(fp) > 1000:
                    os.rename(fp, output_path)
                    return True
        
        return False
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hermes-screenshot.png"
    success = take_screenshot(output)
    if success:
        sz = os.path.getsize(output)
        print(f"OK {output} {sz}")
    else:
        print("FAIL")
        sys.exit(1)
