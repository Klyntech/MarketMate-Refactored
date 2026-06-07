"""
marketmate/execution/bridge.py
───────────────────────────────
Standalone Flask/FastAPI service that wraps MetaAPI.
Runs on port 9000 (internal only).

Migrated from services/metaapi_bridge.py. Updated imports to use
marketmate. prefix where applicable. Logic unchanged.

NOTE: This module requires Flask and metaapi_cloud_sdk. If either
is not installed, the module will still import but app will be None.
Install with: pip install flask metaapi-cloud-sdk
"""

import os
import asyncio

try:
    from flask import Flask, request, jsonify
    from metaapi_cloud_sdk import MetaApi

    app = Flask(__name__)
    _api = MetaApi(os.environ["METAAPI_TOKEN"])


    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}


    @app.route("/test-connection", methods=["POST"])
    def test_connection():
        data = request.json
        try:
            account = asyncio.run(_provision_and_test(
                data["broker"], data["login"], data["password"], data["server"]
            ))
            return jsonify({
                "connected": True,
                "balance": account["balance"],
                "equity": account["equity"],
                "server": account["server"],
                "currency": account["currency"],
                "leverage": account["leverage"],
                "meta_api_account_id": account["id"],
            })
        except Exception as e:
            return jsonify({"connected": False, "error": str(e)}), 400


    async def _provision_and_test(broker, login, password, server):
        acct = await _api.metatrader_account_api.create_account({
            "name": f"{broker}-{login}",
            "type": "cloud",
            "login": login,
            "password": password,
            "server": server,
            "platform": "mt5",
            "application": "RPC",
            "magic": 123456,
        })
        await acct.deploy()
        await acct.wait_connected()
        info = await acct.get_account_information()
        # Attach the meta_api_account_id for storage
        info["id"] = acct.id
        return info


    if __name__ == "__main__":
        app.run(host="127.0.0.1", port=9000, debug=False)

except ImportError:
    # Flask or MetaAPI SDK not installed — bridge is optional
    app = None  # type: ignore[assignment]
