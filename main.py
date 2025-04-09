import logging

from fastapi import BackgroundTasks, FastAPI, Request

from errors import AnnotationDoesNotExist
from handler import IstioHandler
from schemas import AdmissionResponseSchema, ControllerResponseSchema

app = FastAPI()


@app.post("/validate")
async def validate(request: Request, bg_tasks: BackgroundTasks):
    try:
        data = await request.json()
        logging.info(f"Received data: {data}")
        if data["request"]["operation"] in ["CREATE", "UPDATE"]:
            istio_handler = IstioHandler(data["request"]["object"])
            istio_handler.preflight_check()
            bg_tasks.add_task(istio_handler.create_gateway)
            bg_tasks.add_task(istio_handler.create_certificate)
        elif data["request"]["operation"] == "DELETE":
            istio_handler = IstioHandler(data["request"]["oldObject"])
            bg_tasks.add_task(istio_handler.delete_gateway)
        response = ControllerResponseSchema(
            response=AdmissionResponseSchema(
                uid=data["request"]["uid"],
                allowed=True,
                status={
                    "message": "Validation passed",
                },
            )
        )
        logging.info(f"Response: {response}")
        return response

    except AnnotationDoesNotExist as e:
        logging.info(f"Annotation does not exist, hence skipping certificate creation")
        return ControllerResponseSchema(
            response=AdmissionResponseSchema(
                uid=data["request"]["uid"],
                allowed=True,
                status={
                    "message": "Annotation does not exist, skipping certificate creation",
                },
            )
        )

    except Exception as e:
        logging.error(f"Error validating data: {e}")
        return ControllerResponseSchema(
            response=AdmissionResponseSchema(
                uid=data["request"]["uid"],
                allowed=False,
                status={
                    "message": str(e),
                },
            )
        )

@app.post("/delete")
async def delete(request: Request, bg_tasks: BackgroundTasks):
    try:
        data = await request.json()
        istio_handler = IstioHandler(data["request"]["object"])
        bg_tasks.add_task(istio_handler.delete_gateway)
    except Exception as e:
        logging.error(f"Error deleting data: {e}")
        return ControllerResponseSchema(
            response=AdmissionResponseSchema(
                uid=data["request"]["uid"],
                allowed=False,
                status={
                    "message": str(e),
                },
            )
        )
