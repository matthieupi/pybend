
// COde to show all event (on ones only) happening on the window
Object.keys(window).forEach(key => {
    if (/^on/.test(key)) {
        window.addEventListener(key.slice(2), event => {
            console.log(event);
        });
    }
});

