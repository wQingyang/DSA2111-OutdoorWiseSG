
document.addEventListener("DOMContentLoaded", () => {
  const aiInput = document.getElementById("ai-route-input");
  const aiButton = document.getElementById("ai-parse-button");
  const aiStatus = document.getElementById("ai-route-status");

  if (!aiInput || !aiButton || !aiStatus) {
    return;
  }

  aiButton.addEventListener("click", async () => {
    const text = aiInput.value.trim();

    if (!text) {
      aiStatus.textContent = "Please describe your route.";
      return;
    }

    aiButton.disabled = true;
    aiStatus.textContent = "AI is analyzing your request...";

    try {
      const response = await fetch("/api/llm/parse", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "AI request failed."
        );
      }

      // Fill the existing OutdoorWise form.
      document.getElementById("route-distance").value =
        data.target_distance_km;

      document.getElementById(
        "dynamic-target-difficulty"
      ).value = String(data.target_difficulty);

      document.getElementById("route-green").checked =
        data.preferences.prefer_green;

      document.getElementById("route-quiet").checked =
        data.preferences.prefer_quiet;

      document.getElementById("route-steps").checked =
        data.preferences.avoid_steps;

      const locationMessage = data.location
        ? `AI detected "${data.location}". Select its starting point on the map or enter coordinates.`
        : "Keep or adjust the current starting coordinates.";


const form = document.getElementById("route-generator");

if (!form) {
  throw new Error("Route generator form not found.");
}

if (!form.reportValidity()) {
  aiStatus.textContent =
    "Please check the route parameters.";
  return;
}

aiStatus.textContent =
  "AI preferences applied. Generating routes " +
  "from the current map starting point...";

form.requestSubmit();


    } catch (error) {
      aiStatus.textContent =
        `AI parsing failed: ${error.message}`;
    } finally {
      aiButton.disabled = false;
    }
  });
});
