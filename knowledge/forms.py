from django import forms


class KnowledgeImportForm(forms.Form):

    file = forms.FileField(
        required=False,
        help_text=(
            "Upload a JSON, Markdown (.md), or TXT file."
        )
    )

    pasted_content = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 25,
                "placeholder": (
                    "Paste your AB Technologies knowledge here..."
                ),
                "style": (
                    "width:100%;"
                    "font-family:monospace;"
                    "font-size:14px;"
                ),
            }
        ),
    )

    content_type = forms.ChoiceField(
        choices=[
            ("auto", "Auto Detect"),
            ("knowledge", "Knowledge Article"),
            ("service", "Service"),
            ("product", "Product"),
            ("course", "Training Course"),
        ],
        initial="auto",
    )

    def clean(self):

        cleaned_data = super().clean()

        uploaded_file = cleaned_data.get("file")
        pasted_content = cleaned_data.get(
            "pasted_content"
        )

        if not uploaded_file and not pasted_content:
            raise forms.ValidationError(
                "Upload a file or paste some content."
            )

        if uploaded_file:

            filename = uploaded_file.name.lower()

            allowed = (
                filename.endswith(".json")
                or filename.endswith(".md")
                or filename.endswith(".markdown")
                or filename.endswith(".txt")
            )

            if not allowed:
                raise forms.ValidationError(
                    "Supported files are JSON, Markdown and TXT."
                )

        return cleaned_data