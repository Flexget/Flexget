/*
  FlexGet JavaScript

  NOTE: This should contain only code that globally useful, plugin specific code should be added by the plugin!
        Plugins can insert scripts by using head block
*/


/* click on flash should fade out it */

$(document).ready(function() {
    $('#flash').click(function() {
        $('#flash').fadeOut(500);
    });
});


/* category menu javascript */

$(document).ready(function(){
    if ($("#cat")) {
        // TODO: get rid of this hide call, it causes flickering ...
        $("#cat dd").hide();
        $("#cat dt div").addClass("expand");
        $("#cat dt div").click(function() {
            if (this.className.indexOf("expand") >= 0) {
                // hide visible
                $("#cat dd:visible").slideUp(200);

                // reset all to default
                $("#cat dt div").removeClass();
                $("#cat dt div").addClass("expand");

                // set this to shown
                $(this).removeClass();
                $(this).addClass("collapse");

                // show clicked
                $(this).parent().next().slideDown(400);
            }
            else {
                $(this).removeClass();
                $(this).addClass("expand");

                $(this).parent().next().slideUp(150);
            }
            return false;
        });
        //Open up category with a selected item
        var selected = $("#cat dt div.selected");
        if (selected) {
            $(selected).parent().next().show();
            // set state to shown
            $(selected).removeClass();
            $(selected).addClass("collapse");
        }
    }
});

/* menu list element actions */

$(document).ready(function(){

    if ($("#cat")) {
        $("#cat dd ul li div.item").hover(
            function () {
                $(this).find("div.actions").show();
            },
            function () {
                $(this).find("div.actions").hide();
            });
    }

});
