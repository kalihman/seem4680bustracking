var MainBox  = React.createClass({
    render:function(){
        return(
          <div className="ui fluid container">
            <Title/>
            <App/>
          </div>
        );
    }
});
var Title = React.createClass({
    render: function(){
        return(
          <div className="ui vertical masthead center aligned segment">
              <h1 className="ui center aligned header">
                <img className="ui middle aligned tiny image" src="/assets/img/title.png"/>
                <div className="content">SEEM 4680 Demo App</div>
              </h1>
          </div>);
    }
});
var App = React.createClass({
    //setting up initial state
    getInitialState:function(){
        return{
            data:[]
        };
    },
    componentDidMount(){
        this.getDataFromServer('http://52.221.223.238/app/scanner');
    },
    //showResult Method
        showResult: function(response) {

            this.setState({
                data: response
            });
    },
    //making ajax call to get data from server
    getDataFromServer:function(URL){
        $.ajax({
            type:"GET",
            dataType:"json",
            url:URL,
            success: function(response) {
                this.showResult(response);
            }.bind(this),
            error: function(xhr, status, err) {
                console.error(this.props.url, status, err.toString());
            }.bind(this)
        });
    },
    render:function(){
        return(
            <div>
                <Refresh onButtonClick={this.getDataFromServer} />
                <Result result={this.state.data}/>
            </div>
        );
    }
});
var Refresh = React.createClass({
    handleButtonClick: function() {
        this.props.onButtonClick("http://52.221.223.238/scanner");
    }, 
    render: function() {
        return (
          <div className="ui vertical stripe center aligned segment">
            <button className="ui blue button" onClick={this.handleButtonClick}>Update</button>
          </div>);
    }
});
var Result = React.createClass({
    render:function(){
        var result = this.props.result.map(function(result, index){
            return <ResultItem key={index} beacon={ result } />
            });
        return(
            <div className="ui container">
                <div className="ui vertical stripe center aligned segment">
                    <table className="ui celled padded blue table stackable">
                        <thead className="single line">
                            <tr>
                                <th className="ui center aligned">Bus ID</th>
                                <th className="ui center aligned">Station</th>
                                <th className="ui center aligned">Status</th>
                                <th className="ui center aligned">Latest Record</th>
                            </tr>
                        </thead>
                        <tbody>
                            {result}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }
});
var ResultItem = React.createClass({
    render:function(){
        var record = this.props.beacon;
        var timestamp = new Date(parseInt(record.timestamp*1000));
        //var left = new Date(Date.now() - record.timestamp*1000);
        //var left = moment.duration({}, 's').subtract(moment.duration(record.timestamp).seconds();
        var status = record.status === "found" ? "Arrived" : "Left"
        return(
            <tr>
                <td className="ui center aligned">{record.beaconID}</td>
                <td className="ui center aligned">{record.station}</td>
                <td className="ui center aligned">{status}</td>
                <td className="ui center aligned">{timestamp.toLocaleTimeString()}</td>
            </tr>
        );
    }
});
ReactDOM.render(
    <MainBox />,
    document.querySelector("#app")
);
