// Get the window width and update the game form display accordingly
function updateGameFormDisplay() {
  const windowWidth = window.innerWidth;

  if (windowWidth < 600) {
    document.getElementById("game-form-Big").style.display = "none";

    document.getElementById("game-form-Small").style.display = "block";
    //remove the hidden attribute from the small form
    document.getElementById("game-form-Small").removeAttribute("hidden");
    } else {
    document.getElementById("game-form-Small").style.display = "none";
    document.getElementById("game-form-Small").setAttribute("hidden", "true");


    document.getElementById("game-form-Big").style.display = "block";
    //remove the hidden attribute from the big form
    document.getElementById("game-form-Big").removeAttribute("hidden");

  }

// Call the updateGameFormDisplay function on page load
window.addEventListener("load", updateGameFormDisplay);

// Call the updateGameFormDisplay function when the window is resized
window.addEventListener("resize", updateGameFormDisplay);
}
