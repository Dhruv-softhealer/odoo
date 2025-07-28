import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.SHCreateAppointmentPopup = publicWidget.Widget.extend({
    selector: '.o_portal_appointment_form',
    selector: '#createticketModal , .sh_book_btn',

    events: {
        'change #sh_date': '_onDateChange',
        'change #sh_doctor_id':'_onDateChange',
        'click #new_appt':'_onClickNewAppointment',
    },

    _onDateChange: function () {

        // console.log("Hello")
        $.ajax({
            url: "/portal/slotdata",
            data: { sh_date: $("#sh_date").val(),sh_doctor_id: $("#sh_doctor_id").val() },
            type: "post",
            success: function (result) {
                var datas = JSON.parse(result);
                $("#portal_slot > option").remove();
                $("#portal_slot").append('<option value="' + "sub_category" + '">' + "Select slot " + "</option>");
                $.each(datas.sub_categories, function(index, data) {
                    $("#portal_slot").append('<option value="' + data.id + '">' + data.name + "</option>");
                });
            },
        });
    },

    _onClickNewAppointment: function (ev) {
        $("#createticketModal").modal("show");
    },
});
