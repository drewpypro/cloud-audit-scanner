#!/usr/bin/env python3

import os
import json
import re
import subprocess
import argparse
from pathlib import Path
import glob
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

# Precompile regex patterns for better performance
AWS_CREATE_PATTERN = re.compile(r'^(Create|Put|Add|Insert|Register|Provision|Deploy|Upload)')
AWS_UPDATE_PATTERN = re.compile(r'^(Update|Modify|Set|Change|Edit)')
AWS_DELETE_PATTERN = re.compile(r'^(Delete|Remove|Terminate|Deregister|Unregister|Deprovision|Undeploy)')
AWS_READ_PATTERN = re.compile(r'^(Get|Describe|List|Retrieve|Read|Search|Fetch|Find)')
AWS_EXECUTE_PATTERN = re.compile(r'^(Start|Run|Invoke|Execute|Perform|Call|Trigger)')
AWS_STOP_PATTERN = re.compile(r'^(Stop|Halt|Pause|Suspend|Cancel)')
AWS_ENABLE_PATTERN = re.compile(r'^(Enable|Activate|Authorize)')
AWS_DISABLE_PATTERN = re.compile(r'^(Disable|Deactivate|Deauthorize)')
AWS_ASSOCIATE_PATTERN = re.compile(r'^(Associate|Attach|Connect|Link|Bind)')
AWS_DISASSOCIATE_PATTERN = re.compile(r'^(Disassociate|Detach|Disconnect|Unlink|Unbind)')
AWS_VALIDATE_PATTERN = re.compile(r'^(Validate|Verify|Test|Check)')
AWS_TRANSFER_PATTERN = re.compile(r'^(Import|Export|Restore|Backup)')
AWS_TAG_PATTERN = re.compile(r'^(Tag|Untag|Label)')
AWS_COPY_PATTERN = re.compile(r'^(Copy|Clone|Replicate)')
AWS_PROMOTE_PATTERN = re.compile(r'^(Promote|Upgrade|Downgrade)')

# Similar patterns for GCP but with slight differences
GCP_CREATE_PATTERN = re.compile(r'^(Create|Insert|Add|Register|Provision|Deploy|Upload)')
GCP_UPDATE_PATTERN = re.compile(r'^(Update|Patch|Modify|Set|Change|Edit)')
GCP_DELETE_PATTERN = re.compile(r'^(Delete|Remove|Terminate|Deregister|Unregister|Deprovision|Undeploy)')
GCP_READ_PATTERN = re.compile(r'^(Get|List|Describe|Retrieve|Read|Search|Fetch|Find)')
GCP_EXECUTE_PATTERN = re.compile(r'^(Start|Run|Invoke|Execute|Perform|Call|Trigger)')
GCP_STOP_PATTERN = re.compile(r'^(Stop|Halt|Pause|Suspend|Cancel)')
GCP_ENABLE_PATTERN = re.compile(r'^(Enable|Activate|Allow)')
GCP_DISABLE_PATTERN = re.compile(r'^(Disable|Deactivate|Disallow)')
GCP_ASSOCIATE_PATTERN = re.compile(r'^(Attach|Connect|Link|Bind|Associate)')
GCP_DISASSOCIATE_PATTERN = re.compile(r'^(Detach|Disconnect|Unlink|Unbind|Disassociate)')
GCP_VALIDATE_PATTERN = re.compile(r'^(Validate|Verify|Test|Check)')
GCP_TRANSFER_PATTERN = re.compile(r'^(Import|Export|Restore|Backup)')
GCP_TAG_PATTERN = re.compile(r'^(Tag|Untag|Label)')
GCP_COPY_PATTERN = re.compile(r'^(Copy|Clone|Replicate)')
GCP_PROMOTE_PATTERN = re.compile(r'^(Promote|Demote|Upgrade|Downgrade)')
GCP_APPLY_PATTERN = re.compile(r'^(Apply|Use)')

# Generic API method pattern
GENERIC_API_PATTERN = re.compile(r'\b([A-Z][a-z]+[A-Z][a-zA-Z]*)\b')

def determine_aws_operation_type(op_name):
    """Determine operation type with enhanced categorization for AWS operations"""
    # Use precompiled patterns for faster matching
    if AWS_CREATE_PATTERN.match(op_name):
        return "CREATE"
    elif AWS_UPDATE_PATTERN.match(op_name):
        return "UPDATE"
    elif AWS_DELETE_PATTERN.match(op_name):
        return "DELETE"
    elif AWS_READ_PATTERN.match(op_name):
        return "READ"
    elif AWS_EXECUTE_PATTERN.match(op_name):
        return "EXECUTE"
    elif AWS_STOP_PATTERN.match(op_name):
        return "STOP"
    elif AWS_ENABLE_PATTERN.match(op_name):
        return "ENABLE"
    elif AWS_DISABLE_PATTERN.match(op_name):
        return "DISABLE"
    elif AWS_ASSOCIATE_PATTERN.match(op_name):
        return "ASSOCIATE"
    elif AWS_DISASSOCIATE_PATTERN.match(op_name):
        return "DISASSOCIATE"
    elif AWS_VALIDATE_PATTERN.match(op_name):
        return "VALIDATE"
    elif AWS_TRANSFER_PATTERN.match(op_name):
        return "TRANSFER"
    elif AWS_TAG_PATTERN.match(op_name):
        return "TAG"
    elif AWS_COPY_PATTERN.match(op_name):
        return "COPY"
    elif AWS_PROMOTE_PATTERN.match(op_name):
        return "PROMOTE"
    else:
        return "ACTION"

def determine_gcp_operation_type(op_name):
    """Determine operation type with enhanced categorization for GCP operations"""
    # Use precompiled patterns for faster matching
    if GCP_CREATE_PATTERN.match(op_name):
        return "CREATE"
    elif GCP_UPDATE_PATTERN.match(op_name):
        return "UPDATE"
    elif GCP_DELETE_PATTERN.match(op_name):
        return "DELETE"
    elif GCP_READ_PATTERN.match(op_name):
        return "READ"
    elif GCP_EXECUTE_PATTERN.match(op_name):
        return "EXECUTE"
    elif GCP_STOP_PATTERN.match(op_name):
        return "STOP"
    elif GCP_ENABLE_PATTERN.match(op_name):
        return "ENABLE"
    elif GCP_DISABLE_PATTERN.match(op_name):
        return "DISABLE"
    elif GCP_ASSOCIATE_PATTERN.match(op_name):
        return "ASSOCIATE"
    elif GCP_DISASSOCIATE_PATTERN.match(op_name):
        return "DISASSOCIATE"
    elif GCP_VALIDATE_PATTERN.match(op_name):
        return "VALIDATE"
    elif GCP_TRANSFER_PATTERN.match(op_name):
        return "TRANSFER"
    elif GCP_TAG_PATTERN.match(op_name):
        return "TAG"
    elif GCP_COPY_PATTERN.match(op_name):
        return "COPY"
    elif GCP_PROMOTE_PATTERN.match(op_name):
        return "PROMOTE"
    elif GCP_APPLY_PATTERN.match(op_name):
        return "APPLY"
    else:
        return "ACTION"

def run_process(cmd, shell=True, capture_output=True):
    """Helper function to run a process with consistent error handling"""
    try:
        if capture_output:
            result = subprocess.run(
                cmd, 
                shell=shell, 
                check=False,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                universal_newlines=True
            )
            return result.stdout if result.returncode == 0 else None
        else:
            result = subprocess.run(cmd, shell=shell, check=False)
            return result.returncode == 0
    except Exception as e:
        print(f"[-] Error running command: {cmd}\n  {str(e)}")
        return None

def process_aws_service_model(service, service_dir, newest_version):
    """Process a single AWS service model - for parallel execution"""
    try:
        service_model_path = os.path.join(service_dir, newest_version, 'service-2.json')
        
        if not os.path.exists(service_model_path):
            # Try other service model files
            model_files = glob.glob(os.path.join(service_dir, newest_version, 'service-*.json'))
            if not model_files:
                return service, []
            service_model_path = model_files[0]
        
        # Load the service model
        with open(service_model_path, 'r') as f:
            model = json.load(f)
            
        # Extract operations
        operations = model.get('operations', {})
        
        # Process all operations to capture metadata
        all_operations = []
        
        for op_name, op_details in operations.items():
            # Enhanced operation type detection
            op_type = determine_aws_operation_type(op_name)
                
            # Capture operation details
            all_operations.append({
                "operation": op_name,
                "operation_type": op_type,
                "event_source": f"{service}.amazonaws.com",
                "event_name": op_name,
                "input_shape": op_details.get('input', {}).get('shape', ''),
                "output_shape": op_details.get('output', {}).get('shape', ''),
                "errors": [e.get('shape') for e in op_details.get('errors', [])]
            })
        
        return service, all_operations
            
    except Exception as e:
        print(f"[-] Error processing service model for {service}: {str(e)}")
        return service, []

def process_aws_cli_service(aws_cmd_path, service):
    """Process a single AWS CLI service - for parallel execution"""
    try:
        # Get service help
        service_help = run_process([aws_cmd_path, service, 'help'])
        if not service_help:
            return service, []
        
        # Extract operations
        operations = []
        operations_section = False
        for line in service_help.split('\n'):
            if "AVAILABLE COMMANDS" in line:
                operations_section = True
                continue
            elif not line.strip() or "SYNOPSIS" in line:
                if operations_section:
                    operations_section = False
            
            if operations_section and line.strip():
                # Extract operations from the line
                if line.startswith('o '):
                    op = line[2:].strip().split()[0]
                    if op:
                        operations.append(op)
        
        # Process all operations
        all_operations = []
        for op_name in operations:
            # Convert hyphenated command to CamelCase for API event names
            camel_op = ''.join(word.capitalize() if i > 0 else word 
                         for i, word in enumerate(op_name.split('-')))
            
            # Enhanced operation type detection for CLI commands
            op_type = determine_aws_operation_type(op_name.replace('-', ''))
            
            all_operations.append({
                "operation": camel_op,  # API operation name
                "command": op_name,     # CLI command
                "operation_type": op_type,
                "event_source": f"{service}.amazonaws.com",
                "event_name": camel_op
            })
        
        return service, all_operations
                
    except Exception as e:
        print(f"[-] Error processing AWS CLI service {service}: {str(e)}")
        return service, []

def process_gcp_service(service, valid_dirs, sdk_root, crud_patterns):
    """Process a single GCP service - for parallel execution"""
    print(f"[*] Processing GCP service: {service}")
    
    operations = []
    processed_ops = set()  # For deduplication
    
    # Search for CRUD patterns
    for pattern in crud_patterns:
        for api_dir in valid_dirs:
            try:
                # Find all files related to this service with the CRUD pattern
                search_pattern = f"{pattern}[A-Z][a-zA-Z]+"
                cmd = f"grep -r '{search_pattern}' {api_dir} --include='*.py' --include='*.json' --include='*.yaml' | grep -i '{service}' | grep -v '__pycache__'"
                
                output = run_process(cmd)
                if not output:
                    continue
                
                for line in output.split('\n'):
                    if not line.strip():
                        continue
                        
                    parts = line.split(':')
                    if len(parts) < 2:
                        continue
                        
                    file_path = parts[0]
                    content = ':'.join(parts[1:])
                    
                    # Skip tests and non-API files
                    if 'test' in file_path.lower() or 'mock' in file_path.lower():
                        continue
                    
                    # Extract operation name
                    operation_match = re.search(f"({pattern}[A-Z][a-zA-Z]+)", content)
                    
                    if operation_match:
                        operation_name = operation_match.group(1)
                        
                        # Skip if already processed
                        if operation_name in processed_ops:
                            continue
                        
                        processed_ops.add(operation_name)
                        
                        # Determine operation type
                        op_type = determine_gcp_operation_type(operation_name)
                        
                        operations.append({
                            "operation": operation_name,
                            "operation_type": op_type,
                            "service": service,
                            "audit_log_method": f"{service}.{operation_name}",
                            "file_path": os.path.relpath(file_path, sdk_root)
                        })
            except Exception as e:
                print(f"[-] Error processing {service} with pattern {pattern}: {str(e)}")
    
    # Also try to find generic API methods that might not match the patterns
    try:
        for api_dir in valid_dirs:
            cmd = f"grep -r '{service}' {api_dir} --include='*.py' --include='*.json' --include='*.yaml' | grep -v '__pycache__'"
            
            output = run_process(cmd)
            if not output:
                continue
            
            for line in output.split('\n'):
                if not line.strip():
                    continue
                    
                parts = line.split(':')
                if len(parts) < 2:
                    continue
                    
                file_path = parts[0]
                content = ':'.join(parts[1:])
                
                # Skip tests and non-API files
                if 'test' in file_path.lower() or 'mock' in file_path.lower():
                    continue
                
                # Look for potential methods using generic pattern
                for match in GENERIC_API_PATTERN.finditer(content):
                    potential_op = match.group(1)
                    
                    # Skip if already processed
                    if potential_op in processed_ops:
                        continue
                    
                    # Skip if this is a common Python or class name
                    if potential_op in ['Class', 'Type', 'Object', 'Function', 'Method', 
                                      'Property', 'Value', 'Exception']:
                        continue
                        
                    # Check if this looks like a valid API method
                    if len(potential_op) > 5 and not potential_op.startswith(('_', 'Get', 'Set')):
                        processed_ops.add(potential_op)
                        
                        # Determine operation type
                        op_type = determine_gcp_operation_type(potential_op)
                        
                        operations.append({
                            "operation": potential_op,
                            "operation_type": op_type,
                            "service": service,
                            "audit_log_method": f"{service}.{potential_op}",
                            "file_path": os.path.relpath(file_path, sdk_root),
                            "discovery_method": "generic_pattern"
                        })
    except Exception as e:
        print(f"[-] Error during generic pattern search for {service}: {str(e)}")
    
    return service, operations

def scan_aws_sdk_for_all_crud():
    """Scan AWS CLI/SDK files for all operations"""
    print("[+] Scanning AWS SDK for all operations")
    
    results = {}
    max_workers = min(32, multiprocessing.cpu_count() * 2)
    
    try:
        # Find the AWS CLI executable path
        aws_cmd_path = run_process('which aws', shell=True).strip()
        if not aws_cmd_path:
            print("[-] AWS CLI not found")
            return results
            
        print(f"[*] AWS CLI path: {aws_cmd_path}")
        
        # Get the real path (follow symlinks)
        aws_real_path = run_process(['realpath', aws_cmd_path], shell=False)
        if not aws_real_path:
            print("[-] Could not resolve AWS real path")
            return results
            
        aws_real_path = aws_real_path.strip()
        print(f"[*] AWS CLI real path: {aws_real_path}")
        
        # Extract the AWS CLI installation directory
        aws_install_dir = os.path.dirname(os.path.dirname(aws_real_path))
        print(f"[*] AWS CLI installation directory: {aws_install_dir}")
        
        # Define potential botocore data directories
        botocore_dirs = [
            os.path.join(aws_install_dir, 'dist', 'awscli', 'botocore', 'data'),
            os.path.join(aws_install_dir, 'awscli', 'botocore', 'data')
        ]
        
        botocore_dir = None
        for d in botocore_dirs:
            if os.path.exists(d):
                botocore_dir = d
                print(f"[+] Found botocore directory: {botocore_dir}")
                break
                
        if botocore_dir:
            # Get all service directories
            service_dirs = [d for d in os.listdir(botocore_dir) 
                          if os.path.isdir(os.path.join(botocore_dir, d)) and not d.startswith('.')]
            
            total_services = len(service_dirs)
            print(f"[*] Found {total_services} service directories")
            
            # Process services in parallel
            service_models = []
            print(f"[*] Processing AWS services using {max_workers} workers")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for service in service_dirs:
                    service_dir = os.path.join(botocore_dir, service)
                    
                    # Get all version directories
                    version_dirs = [d for d in os.listdir(service_dir) 
                                 if os.path.isdir(os.path.join(service_dir, d))]
                    
                    if not version_dirs:
                        continue
                    
                    # Sort version directories by date (newest first)
                    version_dirs.sort(reverse=True)
                    
                    # Get the newest version
                    newest_version = version_dirs[0]
                    
                    futures.append(
                        executor.submit(
                            process_aws_service_model, 
                            service, 
                            service_dir, 
                            newest_version
                        )
                    )
                
                # Collect results as they complete
                for i, future in enumerate(as_completed(futures)):
                    service, ops = future.result()
                    if ops:
                        results[service] = ops
                    
                    if (i + 1) % 10 == 0:
                        print(f"[*] Processed {i + 1}/{len(futures)} AWS services")
            
            print(f"[+] Successfully processed {len(results)} AWS services with {sum(len(ops) for ops in results.values())} operations")
            return results
        
        # If we didn't get results from the model files, try AWS CLI
        if not results:
            print("[*] Trying AWS CLI help output approach")
            
            # Get AWS help output
            aws_help = run_process([aws_cmd_path, 'help'], shell=False)
            if not aws_help:
                print("[-] Failed to get AWS CLI help output")
                return results
            
            # Extract available services
            services = []
            services_section = False
            for line in aws_help.split('\n'):
                if "Available Services" in line:
                    services_section = True
                    continue
                elif "Available Commands" in line or not line.strip():
                    if services_section:
                        services_section = False
                
                if services_section and line.strip():
                    # Extract service names from the line
                    words = line.strip().split()
                    services.extend([w for w in words if w and w != 'o'])
            
            # Clean up service list
            services = [s for s in services if s and not s.startswith('o') and s != 'help']
            
            print(f"[*] Found {len(services)} services via AWS CLI help")
            
            # Process each service in parallel
            print(f"[*] Processing AWS CLI services using {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for service in services:
                    futures.append(
                        executor.submit(
                            process_aws_cli_service,
                            aws_cmd_path,
                            service
                        )
                    )
                
                # Collect results as they complete
                for i, future in enumerate(as_completed(futures)):
                    service, ops = future.result()
                    if ops:
                        results[service] = ops
                    
                    if (i + 1) % 10 == 0:
                        print(f"[*] Processed {i + 1}/{len(futures)} AWS CLI services")
            
            print(f"[+] Processed {len(results)} AWS services from CLI with {sum(len(ops) for ops in results.values())} operations")
            return results
    
    except Exception as e:
        print(f"[-] Error scanning AWS SDK: {str(e)}")
        return results

def scan_gcp_sdk_for_all_crud():
    """Scan GCP SDK files for all operations"""
    print("[+] Scanning GCP SDK for all operations")
    max_workers = min(32, multiprocessing.cpu_count() * 2)
    
    try:
        # Find gcloud SDK installation directory
        gcloud_path = run_process('which gcloud', shell=True)
        if not gcloud_path:
            print("[-] gcloud CLI not found")
            return {}
            
        gcloud_path = gcloud_path.strip()
        sdk_root = str(Path(gcloud_path).resolve().parent.parent)
        
        # Try to find API definitions
        api_dirs = [
            os.path.join(sdk_root, 'lib', 'googlecloudsdk', 'third_party', 'apis'),
            os.path.join(sdk_root, 'lib', 'surface'),
            os.path.join(sdk_root, 'lib', 'googlecloudsdk', 'api_lib'),
            os.path.join(sdk_root, 'lib', 'googlecloudsdk', 'schemas'),
        ]
        
        valid_dirs = [d for d in api_dirs if os.path.exists(d)]
        
        if not valid_dirs:
            print(f"[-] Could not find GCP SDK API directories. No results for GCP.")
            return {}
            
        print(f"[+] Found GCP SDK directories: {', '.join(valid_dirs)}")
        
        # Dictionary to store results
        results = {}
        
        # Find all GCP service directories - scan all subdirectories without filtering
        service_dirs = set()
        for api_dir in valid_dirs:
            print(f"[*] Scanning for services in: {api_dir}")
            for root, dirs, files in os.walk(api_dir):
                # Identify potential service directories - anything that might be a service
                for dir_name in dirs:
                    # Skip common non-service directories
                    if (dir_name.startswith('_') or 
                        dir_name.startswith('.') or 
                        dir_name in ['test', 'tests', 'utils', 'common', 'base']):
                        continue
                    
                    # Add as a potential service
                    service_dirs.add(dir_name)
        
        print(f"[*] Found {len(service_dirs)} potential GCP services")
        
        # Try to get a complete list of services from gcloud CLI
        try:
            gcloud_services_cmd = [gcloud_path, 'services', 'list', '--available', '--format=json']
            gcloud_services_output = run_process(gcloud_services_cmd, shell=False)
            
            if gcloud_services_output:
                gcloud_services = json.loads(gcloud_services_output)
                
                # Extract service names from the gcloud output
                for service in gcloud_services:
                    if 'serviceName' in service:
                        service_name = service['serviceName'].split('.')[0]
                        service_dirs.add(service_name)
                
                print(f"[*] Added services from gcloud, now have {len(service_dirs)} potential services")
        except Exception as e:
            print(f"[*] Could not get services from gcloud CLI: {str(e)}")
        
        # Expanded CRUD patterns to capture more operation types
        crud_patterns = [
            'Create', 'Get', 'List', 'Update', 'Delete', 'Insert', 'Patch',  # Common CRUD
            'Enable', 'Disable', 'Start', 'Stop', 'Pause', 'Resume',         # State management
            'Import', 'Export', 'Deploy', 'Undeploy', 'Apply', 'Remove',     # Resource lifecycle
            'Attach', 'Detach', 'Associate', 'Disassociate',                 # Relationship management
            'Validate', 'Test', 'Check', 'Verify',                           # Validation
            'Execute', 'Run', 'Invoke', 'Perform',                           # Execution
            'Copy', 'Move', 'Clone', 'Replicate',                            # Transfer
            'Backup', 'Restore', 'Archive', 'Unarchive'                      # Data management
        ]
        
        # Process GCP services in parallel
        print(f"[*] Processing GCP services using {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for service in service_dirs:
                futures.append(
                    executor.submit(
                        process_gcp_service,
                        service,
                        valid_dirs,
                        sdk_root,
                        crud_patterns
                    )
                )
            
            # Collect results as they complete
            for i, future in enumerate(as_completed(futures)):
                service, ops = future.result()
                if ops:
                    results[service] = ops
                
                if (i + 1) % 20 == 0:
                    print(f"[*] Processed {i + 1}/{len(futures)} GCP services")
        
        print(f"[+] Successfully processed {len(results)} GCP services with {sum(len(ops) for ops in results.values())} operations")
        return results
    except Exception as e:
        print(f"[-] Error scanning GCP SDK: {str(e)}")
        return {}

def simplify_operations(db, output_file="crud_operations_simple.json"):
    simplified = []

    # Process AWS operations
    for service_ops in db.get("aws", {}).values():
        for op in service_ops:
            simplified.append({
                "csp": "aws",
                "service": op.get("event_source", ""),
                "action": op.get("event_name", "")
            })

    # Process GCP operations
    for service_ops in db.get("gcp", {}).values():
        for op in service_ops:
            service_domain = op.get("service", "") + ".googleapis.com"
            action = op.get("audit_log_method", "")
            simplified.append({
                "csp": "gcp",
                "service": service_domain,
                "action": action
            })

    with open(output_file, "w") as f:
        json.dump(simplified, f, indent=2)

    print(f"[+] Simplified operation list saved to: {output_file}")




def generate_operation_report(db, output_file="crud_operation_report.json"):
    """Generate a report of operation types found in the database"""
    report = {
        "report_generated": datetime.now().isoformat(),
        "aws": {
            "total_services": len(db.get("aws", {})),
            "total_operations": sum(len(ops) for ops in db.get("aws", {}).values()),
            "by_operation_type": {},
            "services": {}
        },
        "gcp": {
            "total_services": len(db.get("gcp", {})),
            "total_operations": sum(len(ops) for ops in db.get("gcp", {}).values()),
            "by_operation_type": {},
            "services": {}
        }
    }
    
    # Process AWS operations
    aws_op_types = {}
    for service, operations in db.get("aws", {}).items():
        # Add service summary
        service_op_types = {}
        
        for op in operations:
            op_type = op.get("operation_type", "UNKNOWN")
            
            # Count by operation type
            if op_type not in aws_op_types:
                aws_op_types[op_type] = 0
            aws_op_types[op_type] += 1
            
            # Count by service and operation type
            if op_type not in service_op_types:
                service_op_types[op_type] = 0
            service_op_types[op_type] += 1
        
        # Add service summary to report
        report["aws"]["services"][service] = {
            "total_operations": len(operations),
            "by_operation_type": service_op_types
        }
    
    # Add AWS operation type totals
    report["aws"]["by_operation_type"] = aws_op_types
    
    # Process GCP operations
    gcp_op_types = {}
    for service, operations in db.get("gcp", {}).items():
        # Add service summary
        service_op_types = {}
        
        for op in operations:
            op_type = op.get("operation_type", "UNKNOWN")
            
            # Count by operation type
            if op_type not in gcp_op_types:
                gcp_op_types[op_type] = 0
            gcp_op_types[op_type] += 1
            
            # Count by service and operation type
            if op_type not in service_op_types:
                service_op_types[op_type] = 0
            service_op_types[op_type] += 1
        
        # Add service summary to report
        report["gcp"]["services"][service] = {
            "total_operations": len(operations),
            "by_operation_type": service_op_types
        }
    
    # Add GCP operation type totals
    report["gcp"]["by_operation_type"] = gcp_op_types
    
    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"[+] Generated operation report: {output_file}")
    return report

def main():
    parser = argparse.ArgumentParser(description="Cloud CRUD Database Generator")
    parser.add_argument("-o", "--output", default="cloud_crud_database.json", help="Output database file path")
    parser.add_argument("-r", "--report", default="operation_type_report.json", help="Generate operation type report")
    parser.add_argument("--aws-only", action="store_true", help="Only scan AWS SDK")
    parser.add_argument("--gcp-only", action="store_true", help="Only scan GCP SDK")
    parser.add_argument("--update", action="store_true", help="Update existing database file")
    args = parser.parse_args()
    
    # Check if we should update an existing database
    crud_db = {"aws": {}, "gcp": {}}
    if args.update and os.path.exists(args.output):
        try:
            with open(args.output, 'r') as f:
                crud_db = json.load(f)
            print(f"[+] Loaded existing database: {args.output}")
        except Exception as e:
            print(f"[-] Error loading existing database: {str(e)}")
    
    # Scan AWS if not GCP-only
    if not args.gcp_only:
        crud_db["aws"] = scan_aws_sdk_for_all_crud()
        aws_ops = sum(len(ops) for ops in crud_db["aws"].values())
        print(f"[+] Found {len(crud_db['aws'])} AWS services with {aws_ops} operations")
    
    # Scan GCP if not AWS-only
    if not args.aws_only:
        crud_db["gcp"] = scan_gcp_sdk_for_all_crud()
        gcp_ops = sum(len(ops) for ops in crud_db["gcp"].values())
        print(f"[+] Found {len(crud_db['gcp'])} GCP services with {gcp_ops} operations")
    
    # Save the complete database
    with open(args.output, 'w') as f:
        json.dump(crud_db, f, indent=2)
    
    print(f"[+] Complete CRUD database saved to: {args.output}")
    
    simplify_operations(crud_db, "crud_operations_simple.json")

    # Generate operation report
    report = generate_operation_report(crud_db, args.report)
    
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"AWS: {report['aws']['total_services']} services with {report['aws']['total_operations']} operations")
    print("Top AWS operation types:")
    for op_type, count in sorted(report['aws']['by_operation_type'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {op_type}: {count} operations")
    
    print(f"\nGCP: {report['gcp']['total_services']} services with {report['gcp']['total_operations']} operations")
    print("Top GCP operation types:")
    for op_type, count in sorted(report['gcp']['by_operation_type'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {op_type}: {count} operations")

if __name__ == "__main__":
    main()