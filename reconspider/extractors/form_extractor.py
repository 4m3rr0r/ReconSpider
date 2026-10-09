from urllib.parse import urljoin


def extract_forms(selector, base):
    forms = []
    for form in selector.css("form"):
        controls = []
        for control in form.css("input, select, textarea, button"):
            name = control.attrib.get("name")
            if name:
                controls.append(
                    {
                        "name": name,
                        "type": control.attrib.get("type", control.root.tag),
                        "source": "html_form",
                        "location": "query"
                        if form.attrib.get("method", "get").lower() == "get"
                        else "body",
                        "observed": True,
                    }
                )
        forms.append(
            {
                "action": urljoin(base, form.attrib.get("action", base)),
                "method": form.attrib.get("method", "get").upper(),
                "enctype": form.attrib.get("enctype", "application/x-www-form-urlencoded"),
                "parameters": controls,
                "discovered_from": base,
                "submitted": False,
            }
        )
    return forms
