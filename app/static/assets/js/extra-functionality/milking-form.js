var counter = 1;
function add_more_fields(){
    counter = counter+=1
    if (counter<25){
        html='\
            <div class="row" id="row'+counter+'">\
                <div class="col-md-3 px-md-1" >\
                    <input type="text" name="ear_tag'+counter+'" class="form-control" placeholder="Ενώτιο" required>\
                </div>\
                <div class="col-md-3 px-md-1">\
                    <input type="text" name="amount'+counter+'" class="form-control" placeholder="Ποσότητα" required>\
                </div>\
                <div class="col-md-3 px-md-1">\
                <button id="'+counter+'" class="btn btn-primary btn-fab btn-icon btn-round" onclick="remove_fields(this)">\
                <i class="fas fa-trash-alt"></i>\
                </button>\
                </div>\
            </div>'
    var form = document.getElementById('card-body')
    form.insertAdjacentHTML( 'beforeend', html) 
    }
    
    
    
}

    
function remove_fields(button){
    let number = button.id
    let row = document.getElementById('row'+number)
    var answer = window.confirm("Αφαίρεση Εγγραφής?");
    if (answer) {
        row.remove()
    }else{
        pass
    }

}