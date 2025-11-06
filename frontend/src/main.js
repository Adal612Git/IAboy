import "./styles.css";
import { createApp } from "./ui/app.js";

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("app");
  if (!root) {
    throw new Error("No root element found");
  }
  createApp(root);
});
