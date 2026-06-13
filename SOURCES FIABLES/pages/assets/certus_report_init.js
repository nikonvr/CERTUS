/* CERTUS rapports HTML — init Mermaid (MathJax configuré dans le <head> de chaque page). */
document.addEventListener("DOMContentLoaded", function () {
    if (typeof mermaid !== "undefined") {
        mermaid.initialize({
            startOnLoad: true,
            theme: "base",
            themeVariables: {
                primaryColor: "#e0f2fe",
                primaryTextColor: "#0f172a",
                primaryBorderColor: "#0284c7",
                lineColor: "#64748b",
                secondaryColor: "#f1f5f9",
                fontFamily: '"Inter", "Segoe UI", sans-serif',
            },
            flowchart: {
                curve: "basis",
                nodeSpacing: 50,
                rankSpacing: 50,
                padding: 20,
            },
        });
    }
});
