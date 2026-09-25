import os
import io
import json
import streamlit as st

from google import genai
from google.genai import types
from PIL import Image
from supabase import create_client
from dotenv import load_dotenv



# LOAD ENVIRONMENT VARIABLES


load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")



# GEMINI CLIENT


Client = None

if GEMINI_API_KEY:
    Client = genai.Client(api_key=GEMINI_API_KEY)
else:
    st.error("GEMINI_API_KEY is not found in your .env file")



# SUPABASE CLIENT

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )
else:
    st.error("SUPABASE_URL or SUPABASE_KEY is missing from your .env file")



# STREAMLIT PAGE


st.set_page_config(
    page_title="AI Receipt & Documents Scanner",
    layout="wide"
)

st.title("AI Receipt & Documents Scanner")

st.write(
    "Upload your receipt or document and let AI extract and organize the information."
)



# AI PROMPT


AI_PROMPT = """
You are AI Receipt & Document, an intelligent document extraction assistant.

Read the entire uploaded document and extract ALL information that can be reliably read.

Do not guess or invent information. If information is missing or unreadable, use null.

Return ONLY valid JSON.

Use this structure:

{
  "document": {
    "document_type": null,
    "document_date": null,
    "document_number": null,
    "company_name": null,
    "currency": null,
    "payment_method": null,
    "subtotal": null,
    "discount": null,
    "tax": null,
    "total": null,
    "amount_paid": null,
    "balance": null,
    "additional_information": null
  },
  "items": [
    {
      "item_number": 1,
      "description": null,
      "quantity": null,
      "unit_price": null,
      "amount": null,
      "other_details": null
    }
  ]
}

Rules:
- Extract every product, service, transaction, or line item individually.
- Extract all rows from tables.
- Analyze every page.
- Preserve names, dates, numbers, currencies and values exactly as shown.
- Do not guess missing information.
- If information cannot be read, use null.
- If there are no items, return an empty array.
- Put extra information in additional_information.
"""



# IMAGE SETTINGS


FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png"
}



# COLUMNS


left_col, right_col = st.columns([1, 1])


image_bytes = None
mime_type = None
uploaded_file = None



# UPLOAD

with left_col:

    st.subheader("Upload Receipts/Documents")

    uploaded_file = st.file_uploader(
        "Drop your image receipt or document here",
        type=["jpg", "jpeg", "png"]
    )

    if uploaded_file is not None:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="Your Uploaded Document",
            width=400
        )

        save_format = (
            image.format
            if image.format in FORMAT_TO_MIME
            else "JPEG"
        )

        mime_type = FORMAT_TO_MIME[save_format]

        img_byte_arr = io.BytesIO()

        if save_format == "JPEG" and image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        image.save(
            img_byte_arr,
            format=save_format
        )

        image_bytes = img_byte_arr.getvalue()




# AI PROCESSING


with right_col:

    st.subheader("Organized Data")

    if uploaded_file is not None:

        if st.button(
            "Let AI Read It!",
            type="primary",
            disabled=Client is None or supabase is None
        ):

            with st.spinner("AI is reading your document..."):

                try:

                
                    # SEND DOCUMENT TO GEMINI
                   

                    response = Client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=[
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type=mime_type
                            ),
                            AI_PROMPT
                        ]
                    )


                    # CONVERT AI RESPONSE TO JSON
                    

                    ai_text = response.text.strip()

                    # Remove accidental markdown fences
                    if ai_text.startswith("```json"):
                        ai_text = ai_text.replace(
                            "```json",
                            "",
                            1
                        ).strip()

                    if ai_text.endswith("```"):
                        ai_text = ai_text[:-3].strip()

                    extracted_data = json.loads(ai_text)


                    document = extracted_data.get(
                        "document",
                        {}
                    )

                    items = extracted_data.get(
                        "items",
                        []
                    )


                    
                    # SAVE DOCUMENT TO SUPABASE
                    

                    document_data = {
                        "document_type": document.get("document_type"),
                        "document_date": document.get("document_date"),
                        "document_number": document.get("document_number"),
                        "company_name": document.get("company_name"),
                        "currency": document.get("currency"),
                        "payment_method": document.get("payment_method"),
                        "subtotal": document.get("subtotal"),
                        "discount": document.get("discount"),
                        "tax": document.get("tax"),
                        "total": document.get("total"),
                        "amount_paid": document.get("amount_paid"),
                        "balance": document.get("balance"),
                        "additional_information": document.get(
                            "additional_information"
                        )
                    }


                    document_response = (
                        supabase
                        .table("documents")
                        .insert(document_data)
                        .execute()
                    )


                    
                    # GET DOCUMENT ID
                    

                    document_id = document_response.data[0]["id"]


                
                    # SAVE ALL ITEMS
                    

                    if items:

                        item_records = []

                        for item in items:

                            item_records.append({
                                "document_id": document_id,
                                "item_number": item.get(
                                    "item_number"
                                ),
                                "description": item.get(
                                    "description"
                                ),
                                "quantity": item.get(
                                    "quantity"
                                ),
                                "unit_price": item.get(
                                    "unit_price"
                                ),
                                "amount": item.get(
                                    "amount"
                                ),
                                "other_details": item.get(
                                    "other_details"
                                )
                            })


                        supabase \
                            .table("document_items") \
                            .insert(item_records) \
                            .execute()


                
                    # SUCCESS
                    

                    st.success(
                        "Document successfully extracted and saved to Supabase!"
                    )


                    
                    # DISPLAY DOCUMENT DATA
                    

                    st.markdown("# Document Analysis")

                    st.markdown("## Document Information")

                    document_display = {
                        key.replace("_", " ").title(): value
                        for key, value in document.items()
                    }

                    st.table(document_display)


                    
                    # DISPLAY ITEMS
                    

                    if items:

                        st.markdown("## Items / Transactions")

                        st.dataframe(
                            items,
                            use_container_width=True
                        )


                    
                    # SHOW SUPABASE ID
                    

                    st.caption(
                        f"Database Document ID: {document_id}"
                    )


                except json.JSONDecodeError:

                    st.error(
                        "AI returned an invalid JSON response. "
                        "Please try again."
                    )

                except Exception as e:

                    st.error(
                        f"Something went wrong: {e}"
                    )

    else:

        st.info(
            "Waiting for you to upload a document on the left."
        )