
    <script>
        function applyStyles(element, styles) {
            for (var property in styles) {
                if (styles.hasOwnProperty(property)) {
                    element.style[property] = styles[property];
                }
            }
        }

        function toggleContent() {
            var truncatedContent = document.querySelector('.truncated-content');
            var fullContent = document.querySelector('.full-content');
            var readMore = document.querySelector('.read-more');
            
            if (fullContent.style.display === "none") {
                applyStyles(fullContent, {
                    display: "inline"
                });
                applyStyles(truncatedContent, {
                    display: "none"
                });
                applyStyles(readMore, {
                    display: "none"
                });
            } else {
                applyStyles(fullContent, {
                    display: "none"
                });
                applyStyles(truncatedContent, {
                    display: "inline"
                });
                applyStyles(readMore, {
                    display: "inline"
                });
            }
        }
    </script>
