@app.post("/tencent_alert")
async def tencent_alerts(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON body"}

    product = data.get('alarmPolicyInfo', {}).get('policyName', '').split('_')[0]
    if not product:
        product = "TPE"

    result = await process_tencent_alert(data)
    if result.get("status") == "error":
        return {"status": "error", "data": result}

    message = result.get("message", "")
    group_id = "MDA1NDkyNjQ4OTAy"  # 騰訊雲監控專案的小群
    json_msg = {"message": message, "group_id": group_id, "usage": "tencent_alert", "product": product}

    DBA_service_list = ["MySQL", "Redis", "PostgreSQL", "MongoDB", "TcaplusDB", "KeeWiDB", "TCHouse-C",
                        "ClickHouse", "CDWCH", "Elasticsearch", "CKafka", "TDSQL"]

    async with httpx.AsyncClient() as client:
        response = await client.post("http://127.0.0.1:8525/send", json=json_msg)
        if response.status_code != 200:
            return {"status": "error", "message": "Failed to send primary alert"}
        if "NFS_prod_容器服務_Pod" in message:
            wechat_payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }
            #wechat_response = await client.post(
                #"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxxxx",
                #headers={"Content-Type": "application/json"},
                #json=wechat_payload
            #)

            if wechat_response.status_code != 200:
                return {"status": "error", "message": "Failed to send WeChat alert"}

        # Check if any DBA service is mentioned in the message
        if any(service in message for service in DBA_service_list):
            DBA_group_id = "NjMwMDAxNjUwMTAz"  # 雲DB告警小群 for DBA only
            json_msg_DBA = {"message": message, "group_id": DBA_group_id}
            response_DBA = await client.post("http://127.0.0.1:8525/send", json=json_msg_DBA)

            if response_DBA.status_code != 200:
                return {"status": "error", "message": "Failed to send DBA alert"}

    return {"status": "success", "message": "Alert processed and forwarded"}

@app.post("/gcp-webhook")
async def gcp_webhook(request: Request):
    try:
        # Parse the incoming JSON payload
        alert_data = await request.json()

        # Extract relevant information to create a simplified message
        condition_name = alert_data.get("incident", {}).get("condition_name", "Unknown Condition")
        resource_name = alert_data.get("incident", {}).get("resource_name", "Unknown Resource")
        state = alert_data.get("incident", {}).get("state", "Unknown State")

        # Create a simplified alert message
        simplified_message = f"Alert: {condition_name}\nResource: {resource_name}\nState: {state}"

        # Prepare the payload to send to WeChat
        wechat_payload = {
            "msgtype": "text",
            "text": {
                "content": simplified_message
            }
        }

        # Send the alert message to WeChat
        async with httpx.AsyncClient() as client:
            wechat_response = await client.post(
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ff59b501-5bc9-4e76-9e66-d850554ad29f",
                headers={"Content-Type": "application/json"},
                json=wechat_payload
            )

        # Check if the WeChat alert was successfully sent
        if wechat_response.status_code != 200:
            logging.error(f"Failed to send WeChat alert: {wechat_response.text}")
            return {"status": "error", "message": "Failed to send WeChat alert"}

        # Return success response
        return {"status": "received"}
    except Exception as e:
        logging.error(f"Error processing GCP alert: {e}")
        return {"error": "failed to process alert"}
