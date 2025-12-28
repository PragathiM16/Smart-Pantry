function toggle() {
    let p = document.getElementById("password");
    p.type = p.type === "password" ? "text" : "password";
}

fetch("/alerts")
.then(res => res.json())
.then(data => {
    if (data.length > 0) {
        alert("⚠ Items expiring soon: " + data.join(", "));
    }
});
