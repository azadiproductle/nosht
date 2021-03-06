import React from 'react'
import {Link} from 'react-router-dom'
import {Card, CardImg, CardTitle, CardText, CardBody, Row, Col} from 'reactstrap'
import {chunk_array} from './utils'
import EventCards from './events/Cards'


const Category = ({cat}) => {
  return (
    <Col md="4" className="box-container">
      <Link className="index-card" to={`/${cat.slug}/`}>
        <Card>
          <CardImg top width="100%" src={cat.image + '/thumb.jpg'} alt={cat.name} />
          <CardBody>
            <CardTitle>{cat.name}</CardTitle>
            <CardText>
              {cat.description}
            </CardText>
          </CardBody>
        </Card>
      </Link>
    </Col>
  )
}

export default class Index extends React.Component {
  componentDidMount () {
    this.props.setRootState({
      page_title: null,
      background: null,
      extra_menu: null,
      active_page: null,
    })
  }

  render () {
    const categories = this.props.company.categories
    const events = this.props.company.highlight_events
    return (
      <div className="card-grid">
        <div>
          <h1>Highlighted Events</h1>
          <EventCards events={events}/>
        </div>
        <div className="mt-4">
          <h1>Categories</h1>
          {chunk_array(categories, 3).map((chunk, i) => (
            <Row key={i}>
              {chunk.map((cat, j) => <Category cat={cat} key={j}/>)}
            </Row>
          ))}
        </div>
      </div>
    )
  }
}
