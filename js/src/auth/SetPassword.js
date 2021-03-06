import React from 'react'
import {Row, Col} from 'reactstrap'

export default class SetPassword extends React.Component {
  async on_message (event) {
    if (event.origin !== 'null') {
      return
    }

    const data = JSON.parse(event.data)
    if (data.status !== 'success') {
      this.props.setRootState({error: data})
      return
    }
    this.props.history.replace('/login/')
    this.props.set_message({icon: 'key', message: 'Password successfully set, please login.'})
  }

  async componentDidMount () {
    window.addEventListener('message', this.on_message.bind(this))
  }

  render () {
    return [
      <div key="1" className="d-flex justify-content-center">
          <h1 className="text-center">Set Password</h1>
      </div>,
      <Row key="2" className="justify-content-center">
        <Col md="4" className="login">
          <iframe
            title="Set Password"
            frameBorder="0"
            scrolling="no"
            sandbox="allow-forms allow-scripts"
            src={`/iframes/set-password.html${window.location.search}`}/>
        </Col>
      </Row>
    ]
  }
}
