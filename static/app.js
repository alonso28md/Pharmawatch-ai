async function callApi(path, body, resultEl) {
  resultEl.textContent = "Loading...";
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    resultEl.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    resultEl.textContent = "Error: " + err;
  }
}

document.getElementById("ask-button").addEventListener("click", () => {
  callApi(
    "/ask",
    { question: document.getElementById("ask-question").value },
    document.getElementById("ask-result")
  );
});

document.getElementById("report-button").addEventListener("click", () => {
  const deviceClass = document.getElementById("report-device-class").value || null;
  callApi(
    "/report",
    { description: document.getElementById("report-description").value, device_class: deviceClass },
    document.getElementById("report-result")
  );
});
