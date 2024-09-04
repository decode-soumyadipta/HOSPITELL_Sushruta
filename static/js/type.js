const heading = document.getElementById('typewriter');
    const text = heading.innerText;
    let index = 0;

    function typeWriter() {
        if (index < text.length) {
            heading.innerText = text.substring(0, index + 1); // Add the cursor here
            index++;
            setTimeout(typeWriter, 80); // Adjust the delay (in milliseconds) as desired
        }
    }

    // Call the typewriter function
    typeWriter();
    
document.addEventListener('DOMContentLoaded', (event) => {
    document.querySelectorAll('.smoothScroll').forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = e.currentTarget.getAttribute('href');
            if (targetId.startsWith('/#')) {
                e.preventDefault();
                if (window.location.pathname !== '/') {
                    window.location.href = targetId;
                } else {
                    const sectionId = targetId.split('#')[1];
                    document.getElementById(sectionId).scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    });
});


   /*function handleFormSubmission() {
        // Your form submission logic here...
    
        // Set the feedback message
        const feedbackMessage = "Thank you for your message! We'll be in touch soon.";
    
        // Store the message in the hidden input field
        document.getElementById('feedback-input').value = feedbackMessage;
    }
    handleFormSubmission();*/

    
    function applyStyles(element, styles) {
        for (var property in styles) {
            if (styles.hasOwnProperty(property)) {
                element.style[property] = styles[property];
            }
        }
    }

    function applyStyles(element, styles) {
        for (var property in styles) {
            if (styles.hasOwnProperty(property)) {
                element.style[property] = styles[property];
            }
        }
    }

    
    function toggleContent(postId) {
        var truncatedContent = document.querySelector('.truncated-content[data-post-id="' + postId + '"]');
        var fullContent = document.querySelector('.full-content[data-post-id="' + postId + '"]');
        var readMore = document.querySelector('.read-more[data-post-id="' + postId + '"]');
        var showLess = document.querySelector('.show-less[data-post-id="' + postId + '"]');
        
        if (fullContent.style.display === "none") {
            applyStyles(fullContent, { display: "inline" });
            applyStyles(truncatedContent, { display: "none" });
            applyStyles(readMore, { display: "none" });
            applyStyles(showLess, { display: "inline" });
        } else {
            applyStyles(fullContent, { display: "none" });
            applyStyles(truncatedContent, { display: "inline" });
            applyStyles(readMore, { display: "inline" });
            applyStyles(showLess, { display: "none" });
        }
    }

    const button = document.querySelector('button');

button.addEventListener('mousedown', () => {
  button.classList.add('tap-effect');
});

button.addEventListener('mouseup', () => {
  button.classList.remove('tap-effect');
});
