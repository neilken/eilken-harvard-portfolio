import nbformat
import base64
import os

def extract_images_from_notebook(notebook_path, output_folder="extracted_images"):
    """
    Extracts images from the output cells of a Jupyter notebook.

    Args:
        notebook_path (str): The path to the Jupyter notebook file.
        output_folder (str): The folder where extracted images will be saved.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    notebook = nbformat.read(notebook_path, as_version=4)
    image_count = 0

    for cell_idx, cell in enumerate(notebook.cells):
        if cell.cell_type == 'code':
            for output_idx, output in enumerate(cell.outputs):
                if output.output_type == 'display_data':
                    if 'image/png' in output.data:
                        image_data = output.data['image/png']
                        file_extension = 'png'
                    elif 'image/jpeg' in output.data:
                        image_data = output.data['image/jpeg']
                        file_extension = 'jpeg'
                    else:
                        continue

                    # Decode the base64 image data
                    decoded_image = base64.b64decode(image_data)

                    # Save the image
                    notebook_name = os.path.splitext(os.path.basename(notebook_path))[0]
                    image_filename = os.path.join(output_folder, f"{notebook_name}_cell_{cell_idx}_output_{output_idx}.{file_extension}")
                    with open(image_filename, "wb") as f:
                        f.write(decoded_image)
                    image_count += 1
                    print(f"Extracted {image_filename}")

    if image_count == 0:
        print(f"No images found in {notebook_path}.")
    else:
        print(f"Successfully extracted {image_count} images to '{output_folder}' from {notebook_path}.")

if __name__ == "__main__":
    # Extract images from model development notebook
    notebook_path = "notebooks/04_model_development.ipynb"
    if os.path.exists(notebook_path):
        extract_images_from_notebook(notebook_path, output_folder="extracted_images")
    else:
        print(f"Notebook not found: {notebook_path}")

