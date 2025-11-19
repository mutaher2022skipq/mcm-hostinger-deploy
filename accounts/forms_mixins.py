from django import forms

class TailwindFormMixin:
    """
    Automatically applies Tailwind CSS classes to all form fields.
    Keeps a clean, uniform UI for every Django form.
    """
    default_input_class = (
        "w-full border border-gray-300 rounded-lg px-3 py-2 mt-1 "
        "focus:outline-none focus:ring-2 focus:ring-mcmGreen focus:border-mcmGreen "
        "text-gray-800"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Apply base Tailwind class
            existing_classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_classes} {self.default_input_class}".strip()

            # Handle special field types
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-checkbox h-4 w-4 text-mcmGreen border-gray-300 rounded"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = (
                    "w-full border border-gray-300 rounded-lg px-3 py-2 mt-1 bg-white "
                    "focus:outline-none focus:ring-2 focus:ring-mcmGreen focus:border-mcmGreen text-gray-800"
                )
