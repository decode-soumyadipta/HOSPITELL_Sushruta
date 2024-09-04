$(document).ready(function() {
    $('#food_input').on('input', function() {
        let query = $(this).val();
        if (query.length > 0) {
            $.ajax({
                url: '/recommendations',
                method: 'GET',
                data: { query: query },
                success: function(response) {
                    $('#recommendations').empty();
                    response.forEach(function(item) {
                        $('#recommendations').append('<li class="list-group-item recommendation-item">' + item + '</li>');
                    });

                    // Add click event listener to the recommendation items
                    $('.recommendation-item').on('click', function() {
                        let food_name = $(this).text();
                        $('#food_input').val(food_name);
                        $('#recommendations').empty();
                        fetchFoodDetails(food_name);
                    });
                }
            });
        } else {
            $('#recommendations').empty();
        }
    });

    function fetchFoodDetails(food_name) {
        $.ajax({
            url: '/food_details',
            method: 'GET',
            data: { food_name: food_name },
            success: function(response) {
                if (response) {
                    let details = response.details;
                    $('#nutrition-details').html(`
                        <div class="card mb-4">
                            <div class="card-body" style="background-color: rgba(255, 68, 0, 0.074) ;opacity:inherit;">
                                <h5 class="card-title" style="color: rgb(174, 52, 8);"><strong>${details['Description'] || details['name'] || details['Food Name; name']}</strong></h5>
                               <p class="card-text">
                                    ${details['nutri_energy'] ? `
                                        Energy: ${details['nutri_energy']}<br>
                                        Fat: ${details['nutri_fat']}<br>
                                        Saturated Fat: ${details['nutri_satuFat']}<br>
                                        Carbohydrates: ${details['nutri_carbohydrate']}<br>
                                        Sugar: ${details['nutri_sugar']}<br>
                                        Fiber: ${details['nutri_fiber']}<br>
                                        Protein: ${details['nutri_protein']}<br>
                                        Salt: ${details['nutri_salt']}<br>
                                    ` : details['Energy; enerc'] ? `
                                        Energy: ${details['Energy; enerc']}<br>
                                        Moisture: ${details['Moisture; water']}<br>
                                        Ash: ${details['Ash; ash']}<br>
                                        Vitamins: ${details['Vitamins; vit']}<br>
                                        Total Fat: ${details['Total Fat; fat']}<br>
                                    ` : details['Data.Carbohydrate'] ? `
                                        Carbohydrates: ${details['Data.Carbohydrate']}<br>
                                        Protein: ${details['Data.Protein']}<br>
                                        Fats: ${details['Data.Fat.Total Lipid']}<br>
                                        Sugar: ${details['Data.Sugar Total']}<br>
                                        Water: ${details['Data.Water']}%<br>
                                        Iron: ${details['Data.Major Minerals.Iron']}<br>
                                        Zinc: ${details['Data.Major Minerals.Zinc']}<br>
                                        Vitamin C: ${details['Data.Vitamins.Vitamin C']}<br>
                                    ` : 'No detailed nutrition information available.'}
                                </p>
                            </div>
                        </div>
                    `);

                    $('#similar-foods').html('<h4>Other Similar Foods</h4><div class="row"></div>');
                    response.similar_foods.forEach(function(food) {
                        $('#similar-foods .row').append(`
                            <div class="col-md-4">
                                <div class="card mb-4">
                                    <div class="card-body" style="background-color: rgba(255, 68, 0, 0.074) ;opacity:inherit;">
                                        <h5 class="card-title" style="color: rgb(0, 0, 0);"><strong>${food['Description'] || food['name'] || food['Food Name; name']}</strong></h5>
                                       <p class="card-text">
                                            ${food['nutri_energy'] ? `
                                                Energy: ${food['nutri_energy']}<br>
                                                Fat: ${food['nutri_fat']}<br>
                                                Saturated Fat: ${food['nutri_satuFat']}<br>
                                                Carbohydrates: ${food['nutri_carbohydrate']}<br>
                                                Sugar: ${food['nutri_sugar']}<br>
                                                Fiber: ${food['nutri_fiber']}<br>
                                                Protein: ${food['nutri_protein']}<br>
                                                Salt: ${food['nutri_salt']}<br>
                                            ` : food['Energy; enerc'] ? `
                                                Energy: ${food['Energy; enerc']}<br>
                                                Moisture: ${food['Moisture; water']}<br>
                                                Ash: ${food['Ash; ash']}<br>
                                                Vitamins: ${food['Vitamins; vit']}<br>
                                                Total Fat: ${food['Total Fat; fat']}<br>
                                            ` : food['Data.Carbohydrate'] ? `
                                                Carbohydrates: ${food['Data.Carbohydrate']}<br>
                                                Protein: ${food['Data.Protein']}<br>
                                                Fats: ${food['Data.Fat.Total Lipid']}<br>
                                                Sugar: ${food['Data.Sugar Total']}<br>
                                                Water: ${food['Data.Water']}%<br>
                                                Iron: ${food['Data.Major Minerals.Iron']}<br>
                                                Zinc: ${food['Data.Major Minerals.Zinc']}<br>
                                                Vitamin C: ${food['Data.Vitamins.Vitamin C']}<br>
                                            ` : 'No detailed nutrition information available.'}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        `);
                    });
                }
            }
        });
    }
});
