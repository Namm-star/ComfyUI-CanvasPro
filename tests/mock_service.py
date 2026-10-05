"""Manual demo: prints only loopback address. Fake tasks/images; no production calls."""
from test_integration import Service

if __name__ == "__main__":
    service = Service()
    print("CanvasPro mock service:", service.base, flush=True)
    print("Use CANVASPRO_ALLOW_LOCAL_TEST=1 and CANVASPRO_API_KEY=fake-secret in a separate ComfyUI test process.", flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.server_close()
