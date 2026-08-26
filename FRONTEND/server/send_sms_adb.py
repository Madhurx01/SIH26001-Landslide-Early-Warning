import sys
import subprocess
import json
import time
import re
import xml.etree.ElementTree as ET

ADB_PATH = "/home/arjun/.local/bin/adb"

def check_device():
    try:
        out = subprocess.check_output([ADB_PATH, "devices"]).decode("utf-8")
        lines = [line.strip() for line in out.splitlines() if line.strip() and not line.startswith("List")]
        if not lines:
            return {"connected": False, "status": "No device found"}
        device_id, status = lines[0].split("\t")
        return {"connected": True, "device_id": device_id, "status": status}
    except Exception as e:
        return {"connected": False, "error": str(e)}

def find_send_button():
    try:
        subprocess.run([ADB_PATH, "shell", "uiautomator", "dump", "/sdcard/sih_ui_dump.xml"], capture_output=True, timeout=3)
        out = subprocess.check_output([ADB_PATH, "shell", "cat", "/sdcard/sih_ui_dump.xml"]).decode("utf-8", errors="ignore")
        root = ET.fromstring(out)
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "").lower()
            if "send" in desc:
                bounds = node.attrib.get("bounds", "")
                m = re.search(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    return (x1 + x2) // 2, (y1 + y2) // 2
    except:
        pass
    # Calibrated fallback for modern Google Messages on this device
    return 985, 2242

def send_sms(number, message):
    try:
        dev = check_device()
        if not dev.get("connected") or dev.get("status") != "device":
            return {"success": False, "error": f"Phone not connected or unauthorized: {dev.get('status')}"}
        
        # 1. Wake screen & unlock if needed
        subprocess.run([ADB_PATH, "shell", "input", "keyevent", "224"], capture_output=True)
        subprocess.run([ADB_PATH, "shell", "input", "keyevent", "82"], capture_output=True)
        
        # 2. Launch SMS Intent with target number & message
        escaped_msg = message.replace('"', '\\"').replace("'", "\\'")
        cmd_intent = [
            ADB_PATH, "shell", "am", "start",
            "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{number}",
            "--es", "sms_body", f"\"{escaped_msg}\""
        ]
        subprocess.run(cmd_intent, capture_output=True, timeout=5)
        time.sleep(1.0)
        
        # 3. Tap Send button dynamically or at calibrated position
        tap_x, tap_y = find_send_button()
        subprocess.run([ADB_PATH, "shell", "input", "tap", str(tap_x), str(tap_y)], capture_output=True)
        time.sleep(0.5)
        
        # 4. Return to home so screen stays clean
        subprocess.run([ADB_PATH, "shell", "input", "keyevent", "3"], capture_output=True)
        
        return {"success": True, "number": number, "method": "ADB Hardware SIM Auto-Send"}
    except Exception as e:
        return {"success": False, "number": number, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(check_device()))
    elif len(sys.argv) > 2:
        num = sys.argv[1]
        msg = sys.argv[2]
        print(json.dumps(send_sms(num, msg)))
    else:
        print(json.dumps({"error": "Invalid arguments"}))
