import json, subprocess
from api.mysql import MYSQLSeatalk
from Data.secrets import GSIS_MYSQL_LOGIN

async def process_tencent_alert(data: dict):
	try:
		product = data.get('alarmPolicyInfo', {}).get('policyName', '').split('_')[0]

		alarm_status = data.get('alarmStatus', '')
		if data.get('alarmType') == "metric":
			# Extract the values from the JSON data
			policyName = data.get('alarmPolicyInfo', {}).get('policyName', '')
			metric_show_name = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('metricShowName', '')
			calcType = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('calcType', '')
			calcValue = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('calcValue', '')
			unit = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('unit', '')
			if unit == "None":
				unit = ""
			alert = f"{policyName} {metric_show_name} {calcType} {calcValue}{unit}"
			currentValue = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('currentValue', '')
			obj_name = data.get('alarmObjInfo', {}).get('dimensions', {}).get('objName', '')
			service = obj_name.replace('|', '\t\n')
			region = data.get('alarmObjInfo', {}).get('region', '')
			namespace = data.get('alarmObjInfo', {}).get('namespace', '')
			time = data.get('firstOccurTime', '')
			link = ""
			TENCENT_URL = "https://console.cloud.tencent.com"
   
			if namespace == "qce/cls":
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('grpid', '')
				service = obj_name.split('#')[1] if '#' in obj_name else obj_name
			elif namespace == "qce/cdb":
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('uInstanceId', '')
				link = f"{TENCENT_URL}/cdb/instance/detail?ins=9-{instance_id}&tab=monitor"
			elif "qce/redis" in namespace:
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('objId', '')
				link = f"{TENCENT_URL}/redis/instance/manage/monitor?instanceId={instance_id}&regionId=9"
			elif "qce/cmongo" in namespace:
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('objId', '')
				link = f"{TENCENT_URL}/mongodb/instance/manage/monitor?instanceId={instance_id}&regionId=9"
			elif namespace == "qce/postgres":
				parts = obj_name.split(':')
				instance_id = parts[1].split('|')[0]
				link = f"{TENCENT_URL}/postgres/instance/monitor?region=ap-singapore&instanceId={instance_id}"
			elif "qce/nat" in namespace:
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('objId', '')
				link = f"{TENCENT_URL}/vpc/nat/detail?rid=9&id={instance_id}&tab=monitor"
			elif "qce/ckafka" in namespace:
				instance_id = data.get('alarmObjInfo', {}).get('dimensions', {}).get('instance_id', '')
				link = f"{TENCENT_URL}/ckafka/detail?rid=9&id={instance_id}&tab=monitor&rankType=INSTANCE_EVENT"
			elif "qce/tgw_set" in namespace:
				tmp_string = data.get('alarmObjInfo', {}).get('dimensions', {}).get('objName', '')
				if tmp_string.startswith("Name"):
					name_part = tmp_string.split('|')[0]
					clb_name = name_part.split(':')[1]
					php_result = subprocess.run(['/usr/bin/php', "/opt/tools/NOC_seatalkbot/Scripts/clb_check.php", clb_name], capture_output=True, text=True)
					instance_id = php_result.stdout.strip()
				else:
					name_part = tmp_string.split('|')[1]
					clb_name = name_part.split(':')[1]
					php_result = subprocess.run(['/usr/bin/php', "/opt/tools/NOC_seatalkbot/Scripts/clb_check.php", clb_name], capture_output=True, text=True)
					instance_id = php_result.stdout.strip()
				
				link = f"{TENCENT_URL}/clb/detail?rid=9&id={instance_id}&tab=monitor"
			else:
				link = ""

			if link == "":
				# Build the message to be logged for metric
				message = '\n'.join([
					"Tencent Cloud alert：",
					'- - - - - - -',
					f"Alert : {alert}",
					f"Current Value : {currentValue}{unit}",
					f"Service Info : \n{service}",
					f"Region : {region}",
					f"namespace : {namespace}",
					f"Time : {time}",
				])
			else:
				# Build the message to be logged for metric
				message = '\n'.join([
					"Tencent Cloud alert：",
					'- - - - - - -',
					f"Alert : {alert}",
					f"Current Value : {currentValue}{unit}",
					f"Service Info : \n{service}",
					f"Region : {region}",
					f"namespace : {namespace}",
					f"Time : {time}",
					f"Link : {link}",
				])

		elif data.get('alarmType') == "event":
			# Handle event-type alarms
			productShowName = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('productShowName', '')
			eventShowName = data.get('alarmPolicyInfo', {}).get('conditions', {}).get('eventShowName', '')
			alert = f"{productShowName} {eventShowName}"
			service = data.get('alarmObjInfo', {}).get('dimensions', {}).get('unInstanceId', '')
			region = data.get('alarmObjInfo', {}).get('region', '')
			time = data.get('firstOccurTime', '')

			policyName = data.get('alarmPolicyInfo', {}).get('policyName', '')

			# Build the message to be logged for event
			message = '\n'.join([
				"Tencent Cloud Event alert：",
				'- - - - - - -',
				f"Alert : {alert}",
				f"Service : {service}",
				f"Region : {region}",
				f"Time : {time}",
				f"Alert Policy : {policyName}",
			])
		else:
			alarm_status = '1'

		if alarm_status != '0':

			gsis_db = MYSQLSeatalk(GSIS_MYSQL_LOGIN)
			gsis_db.execute_query(
				"INSERT INTO gsis.tencent_monitoring_alerts (project, instance, alert_name, event_time) VALUES (%s, %s, %s, %s)",
				(product, service, alert, time)
			)

			return {"status": "success", "message": message, "product": product}

	except Exception as e:
		return {"status": "error", "message": str(e)}

