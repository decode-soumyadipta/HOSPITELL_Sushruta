document.addEventListener('DOMContentLoaded', function() {
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('success') === 'true') {
        var cheersAnimation = document.getElementById('cheers-animation');
        cheersAnimation.style.display = 'block';

        // Hide the animation after 2 seconds
        setTimeout(function() {
            cheersAnimation.style.display = 'none';
        }, 2000);
    }
});
